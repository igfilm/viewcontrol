import abc
import importlib
import inspect
import os
import pickle
import pkgutil
import queue
import re
from shutil import copyfile

import pynput
import sqlalchemy
from moviepy.video.VideoClip import ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.resize import resize
from moviepy.video.io.VideoFileClip import VideoFileClip
from numpy import array, arange
from sqlalchemy import (Column, Integer, String, Boolean, ForeignKey,
                        Float, Binary)
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base
from wand.color import Color
from wand.drawing import Drawing
from wand.image import Image

from viewcontrol.remotecontrol.threadcommunicationbase import ComType

Base = declarative_base()


"""
While Modules can only exist in one show (property sequence_name), 
Elements and Objects are not connected to a given show, and can be reused in 
all shows, changing them will track the traces through all shows.
"""


class ShowOptions:
    """Option object for all show specific options.

    Holds all options of the loaded shows. Including connection info
    (ip-address, port, protocol) to known devices.

    Loads all devices defined in remotecontrol subclasses with default
    settings if not already in the device dictionary list. Which can
    than be edited by the user.

    """

    def __init__(self, session):
        """Create a ViewControl object with the given options.

        Args:
            session (orm.session.Session): session object connected to
                database file

        """
        self._session = session
        self._devices = list()
        self._elements_load_from_db()

        package = importlib.import_module("viewcontrol.remotecontrol")
        for _, modname, ispkg in pkgutil.iter_modules(package.__path__):
            if ispkg:
                try:
                    mod = importlib.import_module(
                        "viewcontrol.remotecontrol.{}.threadcommunication"
                        .format(modname))
                except ModuleNotFoundError:
                    continue
                clsmembers = inspect.getmembers(mod, inspect.isclass)
                for clsm in clsmembers:
                    x = clsm[1].mro()
                    if len(x) > 5:
                        if not clsm[0] in self.devices.keys():
                            print("adding " + clsm[0])
                            self._add_device(clsm[1])

    @property
    def devices(self):
        device_dict = dict()
        for device in self._devices:
            device_dict.update({device.name: device})
        return device_dict

    def _add_device(self, device_class):
        """add device to device dictionary

        Adds a device to the device dictionary by parsing a subclass of
        ThreadCommunicationBase to a ShowOptionDevice object.

        Args:
            device_class (ThreadCommunicationBase): class object device

        """
        dev = ShowOptionDevice(device_class)
        self._devices.append(dev)
        self._session.add(dev)
        self._session.commit()

    def _elements_load_from_db(self):
        """load device dictionary from database"""
        self._devices.extend(self._session.query(ShowOptionDevice).all())

    def set_device_property(self, device, enabled=None, connection=None):
        """sets connection property of a device in device dictionary

        Args:
            device    (ShowOptionDevice):
            enabled               (bool): True, enable device
            connection (tuple(str, int)): ip-address as string in the
                form XXX.XXX.XXX.XXX and port as int

        Returns:
            bool: True for success, False otherwise.

        """
        if not enabled and not connection:
            return False
        if enabled:
            device.enabled = enabled
        if connection:
            device.connection = connection
        self._session.commit()
        return True


class ShowOptionDevice(Base):
    """Option object for single device

    Holds connection and enabled options of for a single device defined
    in remotecontrol.

    """

    __tablename__ = 'show_option_device'
    _id = Column(Integer, primary_key=True, name='id')
    _name = Column(String(50), name="name")
    _ip_address = Column(String(15), name="ip_address")
    _port = Column(Integer, name="port")
    _enabled = Column(Boolean, default=False, name="enabled")
    _protocol = Column(String(50), name="protocol")
    _dev_class = Column(String(100), name="dev_class")

    @property
    def name(self):
        return self._name

    @property
    def connection(self):
        return (self._ip_address, self._port)

    @connection.setter
    def connection(self, tuple_ip_port):
        self._ip_address = tuple_ip_port[0]
        self._port = tuple_ip_port[1]

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, enabled):
        self._enabled = enabled

    @property
    def dev_class(self):
        return self._dev_class

    def __init__(self, device_class):
        """Create a ShowOptionDevice object with the given options.

        Args:
            device_class (ThreadCommunicationBase): class object device

        """
        self._name = device_class.__name__
        self._protocol = device_class.mro()[0].__module__.split('.')[2]
        self._dev_class = str(device_class)


class ManagerBase(abc.ABC):
    """Base class for all managers at runtime and in database.

    Objects to be managed must have the attribute _name.

    Attributes:
        session (sqlalchemy.orm.Session): database session
        elements          (list<object>): list of all managed objects

    """

    def __init__(self, session):
        """Create a ManagerBase object with the given options.

        Args:
            session  (sqlalchemy.orm.Session): database session

        """
        self._session = session
        self._elements = []
        self._elements_load_from_db()

    @property
    def session(self):
        return self._session

    @property
    def elements(self):
        return self._elements

    def element_add(self, element):
        """add media element to database,

        if name already exists append a number to the name

        Args:
            element (element): any object to be managed in derived class

        """
        element.name = self._check_name_exists(element.name, obj=element)
        self._elements.append(element)
        self._session.add(element)
        self._session.commit()
        return True

    def element_delete(self, element):
        """add media element to database,

                if name already exists append a number to the name

                Args:
                    element (element): any object to be managed in derived class

        """
        return False

    def element_rename(self, element, new_name, commit=True):
        """rename name of element managed by manager

        Args:
            element           (object): object to be renamed
            new_name             (str): new name for object
            commit    (bool, optional): commits to database if True,
                                        defaults to True

        """
        element.name = self._check_name_exists(new_name, obj=element)
        if commit:
            self._session.commit()
        return True

    def element_get_with_name(self, name):
        """returns element object with given name

        Args:
            name (str): name of string

        Returns:
            object: element with given name, None if no element exits

        """
        for e in self._elements:
            if e.name == name:
                return e
        return None

    def _check_name_exists(self, name, num=1, obj=None):
        """modify given name to be unique if not

        Checks if name already exists. Returns the name unchanged if not in
        database. Else add an number after the name to make it unique.
        Increases the number when number already exists.

        Args:
            name (str): name to be checked
            num  (int): number to try first, internal use in recursion
            obj  (obj): object to be renamed, prohibits wrong renaming,
                when object already exists and when copying.

        Returns:
            str: unique name in managed list

        """
        if num > 1:
            name = '{}_{}'.format(name, num)
        name_exists = self._elements_get_with_name_from_db(name)
        if name_exists:
            if obj and obj.id == name_exists.id:
                return name
            name = self._check_name_exists(name, num=num+1)
        return name

    def _elements_load_from_db(self):
        """load elements from database"""
        self.elements.extend(self._elements_get_all_from_db())

    @abc.abstractmethod
    def _elements_get_with_name_from_db(self, name):
        """returns all elements with given name

        Args:
            name (str): name of object to be loaded

        Returns:
            object: object with given name

        """
        pass

    @abc.abstractmethod
    def _elements_get_by_id_from_db(self, id):
        """returns all elements with given name

        Args:
            id (int): id of object to be loaded

        Returns:
            object: object with given id

        """
        pass

    @abc.abstractmethod
    def _elements_get_all_from_db(self):
        """returns all elements from database

        Returns:
            object: object with given id
        """
        pass


class LogicElement(Base):
    """Base class for Logic Elements.

    Logic elements control the flow of the media elements. They are
    displayed and edited like media elements in Sequence Modules.

    Attributes:
        name    (str): name of the logic element
        key     (int): unique key of logic element (important for loops)
        id      (int): primary key of object in database
        etyp (string): polymorphic_identity of element in database

    """
    __tablename__ = 'logic_element'
    _id = Column(Integer, primary_key=True, name="id")
    _name = Column(String(50), name="name", unique=True)
    _key = Column(Integer, name="key")
    _etype = Column(String(20), name="etype")

    __mapper_args__ = {
        'polymorphic_on': _etype,
        'polymorphic_identity': 'LogicElement'
    }

    def __init__(self, name, key):
        """Create a LogicElement object with the given options.

        Args:
            name (str): name of the logic element
            key  (int): unique key of logic element (important for loops)
        """
        self.name = name
        self._key = key

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        if not name[0] == '#':
            name = '#' + name
        self._name = name

    @property
    def key(self):
        return self._key

    def __repr__(self):
        return "{:04d}|{}|{}".format(self.id, type(self), self.name)


class LoopStart(LogicElement):
    """Saves position for the start of a loop condition"""

    __mapper_args__ = {
        'polymorphic_identity':'LoopStart'
    }

    def __init__(self, name, key):
        super().__init__(name, key)


class LoopEnd(LogicElement):
    """Saves position for the start of a loop condition"""

    _cycles = Column(Integer, name="cycles")

    __mapper_args__ = {
        'polymorphic_identity':'LoopEnd'
    }

    def __init__(self, name, key, cycles):
        super().__init__(name, key)
        self._cycles = cycles
        self.init2()

    @orm.reconstructor
    def init2(self):
        self.counter = 0

    @property
    def cycles(self):
        return self._cycles


class JumpToTarget(LogicElement):
    """When event is triggered, changes current position to its positon"""

    _name_event = Column(String(20), name="name_event")

    __mapper_args__ = {
        'polymorphic_identity':'JumpToTarget'
    }

    def __init__(self, name, name_event):
        self._name_event = name_event
        super().__init__(name, None)

    @property
    def name_event(self):
        return self._name_event


class Barrier(LogicElement):
    """blocking funtion in show until event happens"""
    __mapper_args__ = {
        'polymorphic_identity':'Barrier'
    }


class BarrierEvent(Barrier):

    __mapper_args__ = {
        'polymorphic_identity':'BarrierEvent'
    }

class BarrierTime(Barrier):

    __mapper_args__ = {
        'polymorphic_identity':'BarrierTime'
    }


class LogicElementManager(ManagerBase):
    """Manager for all lofic elemets at runtime and in database.

    Args:
        session (sqlalchemy.orm.Session): database session

    Attributes:
        session  (sqlalchemy.orm.Session): database session
        elements     (Lits<LogicElemets>): list of active logic elemets

    """

    def _elements_get_with_name_from_db(self, name):
        return self.session.query(LogicElement) \
            .filter(LogicElement._name==name).first()

    def _elements_get_by_id_from_db(self, id):
        return self._session.query(LogicElement)\
            .filter(LogicElement._id==id).first()

    def _elements_get_all_from_db(self):
        return self.session.query(LogicElement).all()

    def element_make_loop_pair(self, cycles):
        """make a pair of loop elements 
        which will be added to the list via add_element by the calling function
        """
        raw_key = self.session.query(LoopStart._key) \
            .order_by(sqlalchemy.desc(LoopStart._key)).first()
        if not raw_key:
            key = 1
        else:
            key = raw_key[0]
        loop_start = LoopStart("LoopStart_{}".format(key), key)
        loop_end = LoopEnd("LoopEnd_{}".format(key), key, cycles)
        return loop_start, loop_end


class MediaElement(Base):
    """Base class for Media Elements.

    Since the media output format is always 1080p with an aspect ratio of 16:9, 
    the film format of the film on the BlueRay is either 16:9 widescreen or 
    21:9 cincescope (the term CinemaScope originally stands for a special 
    process for recording and projecting wide-screen films with an aspect ratio
    of 2.55:1 = 23:9 and is nevertheless used here for the designation of the 
    21:9 image format). If the film format is cinescope, the zoom of the 
    projector is adjusted in such a way that the film content fills the screen 
    and the black bars remain outside of the screen. If images and videos are 
    displayed here now, they have to stay in the cinescope image area. 
    Therefore, there are file paths to both media formats, which can also be 
    identical. 

    The following nomenclatures for the image content format are used: 
        cinescope   '21:9'  '_c'
        widescreen  '16:9'  '_w'

    Args:
        name        (str): name of the media element
        file_path_w (str): file path to widescreen version of the file
        file_path_c (str): file path to cinescope version of the file

    Attributes:
        name        (str): name of the media element
        file_path_w (str): file path to widescreen version of the file
        file_path_c (str): file path to cinescope version of the file
        id          (int): primary key of object in database
        etype    (string): polymorphic_identity of element in database

    """
    __tablename__ = 'media_element'
    _id = Column(Integer, primary_key=True, name="id")
    _name = Column(String(20), name ="name", unique=True)
    _file_path_w = Column(String(200), name="file_path_w")
    _file_path_c = Column(String(200), name="file_path_c")
    _etype = Column(String(10), name="etype")

    __mapper_args__ = {
        'polymorphic_on':_etype,
        'polymorphic_identity':'MediaElement'
    }

    project_path = None
    content_aspect_ratio = 'widescreen'
    # for debuging only
    _skip_high_workload_functions = False

    @classmethod
    def set_project_path(cls, path):
        cls.project_path = os.path.expanduser(path)

    @classmethod
    def set_content_aspect_ratio(cls, ratio):
        if ratio in ['w', 'widescreen', '16:9']:
            cls.content_aspect_ratio = 'widescreen'
        else:
            cls.content_aspect_ratio = 'cinescope'

    @staticmethod
    def _create_abs_filepath(abs_source, mid, extension, num=1):
        """create filepath from source filename. if filename already exists,
        add a number at the end.
        """
        target_file_core = os.path.splitext(os.path.basename(abs_source))[0]
        if num > 1:
            midnum = "{}_{}".format(mid, num)
        else:
            midnum = mid
        target_file = os.path.join(
            MediaElement.project_path,
            target_file_core + midnum + extension
        )
        if os.path.exists(target_file):
            return MediaElement._create_abs_filepath(
                abs_source, mid, extension, num=num+1)
        else:
            return target_file, \
                os.path.relpath(target_file, start=MediaElement.project_path)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def file_path(self):
        if MediaElement.content_aspect_ratio == 'widescreen':
            return os.path.join(MediaElement.project_path, self._file_path_w)
        else:
            return os.path.join(MediaElement.project_path, self._file_path_c)


    def __init__(self, name, file_path_w, file_path_c):
        self._name = name
        self._file_path_w = file_path_w
        self._file_path_c = file_path_c

    def __repr__(self):
        return "{:04d}|{}|{}".format(self.id, type(self), self.name)


class VideoElement(MediaElement):
    """Class for moving MediaElement.
    
    Args:
        name        (str): name of the media element
        file_path (str): file path to source file, which will be copied and/or
            converted into the media folder defined in the config file

    Attributes:
        duration (float): duration in seconds of video clip

    """

    _duration = Column(Integer, name="duration")

    __mapper_args__ = {
        'polymorphic_identity':'VideoElement'
    }

    def __init__(self, name, file_path, t_start=0, t_end=None):

        adst_c, rdst_c = \
            MediaElement._create_abs_filepath(file_path, "_c", ".mp4")
        dur, car = self._insert_video(file_path, adst_c,
            cinescope=True,
            t_start=t_start,
            t_end=t_end)
        self._duration = dur
        content_aspect_ratio = car
        if content_aspect_ratio == '21:9':
            adst_w = adst_c
            rdst_w = rdst_c
        else:
            adst_w, rdst_w = \
                MediaElement._create_abs_filepath(file_path, "_w", ".mp4")
            self._insert_video(file_path, adst_w,
                content_aspect=content_aspect_ratio,
                cinescope=False,
                t_start=t_start,
                t_end=t_end)
        super().__init__(name, rdst_w, rdst_c)

    @property
    def duration(self):
        return self._duration

    def _insert_video(self,
            path_scr,
            path_dst,
            content_aspect=None,
            cinescope=True,
            t_start=0,
            t_end=None):
        """convert source file and save it in project directory"""
        if MediaElement._skip_high_workload_functions:
            open(path_dst, 'a').close()
            return 42, "16:9"

        video_clip = VideoFileClip(path_scr).subclip(t_start=t_start, t_end=t_end)
        if cinescope:
            content_aspect = VideoElement._get_video_content_aspect_ratio(video_clip)
        if content_aspect == "16:9" and cinescope:
            #else do nothing cinscope identical with widescreen
            cclip = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=video_clip.duration)
            video_clip = video_clip.fx(resize, height=810).set_position('center')
            result = CompositeVideoClip([cclip, video_clip])
            result.write_videofile(path_dst,fps=video_clip.fps, codec='libx265', preset="superfast")
        elif t_start>0 or t_end:
            video_clip.write_videofile(path_dst,fps=video_clip.fps, codec='libx265', preset="superfast")
        else:
            copyfile(path_scr, path_dst)
        return video_clip.duration, content_aspect

    @staticmethod
    def _get_video_content_aspect_ratio(video_file_clip):
        """anyalyse video for the aspect ratio of its content"""
        vfc = video_file_clip
        samples=5
        sample_time_step = video_file_clip.duration/samples
        w = []
        for t in arange(0,video_file_clip.duration,sample_time_step):
            frame=video_file_clip.get_frame(t)

            w.append(frame[[int(vfc.h*.125), int(vfc.h*.5), int(vfc.h*.875)], 0:vfc.w].mean(axis=2).mean(axis=1))
        w=array(w)
        wm = w.mean(axis=0)

        if wm[0] < 1 and wm[2] < 1 and wm[1]>=1:
            return '21:9'
        else:
            return '16:9'


class TextElement(MediaElement):
    """Class for custom-text MediaElement.

    Args:
        name (str): name of the media element
        text (str): test displayed at playback
    
    """

    __mapper_args__ = {
        'polymorphic_identity':'TextElement'
    }

    def __init__(self, name, text):
        if name[0] != '~':
            name = '~' + name
        filename = '_' + name[1:] + ".jpg"
        super().__init__(name, filename, filename)
        self._text = text
        self._make_text_image(text, self.file_path)

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, new_text):
        self._text = new_text
        self._make_text_image(self.text, self.file_path)

    @staticmethod
    def _make_text_image(text, path_dst):
        """create image with given text and save in project folder"""
        if MediaElement._skip_high_workload_functions:
            open(path_dst, 'a').close()
            return

        with Drawing() as draw:
            with Image(width=1920, height=1080, background=Color("black")) as image:
                #draw.font = 'wandtests/assets/League_Gothic.otf'
                draw.font_size = 100
                draw.stroke_color = "white"
                draw.fill_color = "white"
                draw.text_alignment = 'center'
                draw.text(int(image.width / 2), int(image.height / 2), text)
                draw(image)
                image.save(filename=path_dst)


class StillElement(MediaElement):
    """Class for non-moving MediaElement.

    Args:
        name        (str): name of the media element
        file_path (str): file path to source file, which will be copied and/or
            converted into the media folder defined in the config file

    
    """

    __mapper_args__ = {
        'polymorphic_identity':'StillElement'
    }

    def __init__(self, name, file_path):
        #TODO add handling for gifs if possible
        _, file_extension = os.path.splitext(file_path)
        if not file_extension == '.gif':
            file_extension = ".jpg"
        adst_w, rdst_w = MediaElement._create_abs_filepath(file_path, "_w", file_extension)
        adst_c, rdst_c = MediaElement._create_abs_filepath(file_path, "_c", file_extension)
        StillElement._insert_image(file_path, adst_w , False)
        StillElement._insert_image(file_path, adst_c, True)
        super().__init__(name, rdst_w, rdst_c)


    @staticmethod
    def _insert_image(path_scr, path_dst, cinescope):
        """Composes images with black background for widescreen and cinescope.

            To many gif frames are causing a segmentation fault!!
        """
        if MediaElement._skip_high_workload_functions:
            open(path_dst, 'a').close()
            return

        if cinescope:
            screesize =  (1920, 810)
        else:
            screesize =  (1920, 1080)

        max_upscale = 10

        #check size, if pdf calc resulution to import it in the needed size
        with Image(filename=path_scr, width=1920) as tmp_scr:
            a = screesize[0]/tmp_scr.width
            b = screesize[1]/tmp_scr.height
            scale = min(a, b)
            if max_upscale and scale > max_upscale:
                scale = max_upscale
            s_size = (int(tmp_scr.width * scale), int(tmp_scr.height * scale))

            if tmp_scr.mimetype == "application/pdf":
                res = (tmp_scr.resolution[0] * scale, tmp_scr.resolution[1] * scale)
                scale = 1
            else:
                res = None

        with Image(filename=path_scr, resolution=res) as scr:
            scr.colorspace = 'rgb'
            scr.format = 'jpeg'

            if not scr.mimetype == "image/gif":
                with Image(width=1920, height=1080, background=Color("black")) as dst:
                    if not scale == 1:
                        scr.scale(*s_size)
                        #img.resize(*s_size)
                    offset_width = int((dst.width-scr.width)/2)
                    offset_height = int((dst.height-scr.height)/2)
                    dst.composite(operator='over', left=offset_width, top=offset_height, image=scr)
                    dst.save(filename=path_dst)
            else:
                raise Exception("Gifs are not allowed atm")


class StartElement(MediaElement):
    """Class for start MediaElement cointaining the program picture."""

    def __init__(self):
        super().__init__('viewcontrol', 'media/viewcontrol.png', 'media/viewcontrol.png')


class MediaElementManager(ManagerBase):
    """Manager for all media elemets at runtime and in database.

    Args:
        session (sqlalchemy.orm.Session): database session

    Attributes:
        session  (sqlalchemy.orm.Session): database session
        elements     (Lits<MediaElemets>): list of active media elemets

    """

    def _elements_get_with_name_from_db(self, name, num=1):
        return self._session.query(MediaElement)\
            .filter(MediaElement._name==name).first()

    def _elements_get_by_id_from_db(self, id):
        return self._session.query(MediaElement)\
            .filter(MediaElement._id==id).first()

    def _elements_get_all_from_db(self):
        return self._session.query(MediaElement).all()


class SequenceModule(Base):
    """Object of a Playlist

    One of the two elements is always None (construction for database technical
    reasons). A MediaElement can be used in any number of SequenceElements 
    (many to one). With VideoElements the time corresponds to the video length 
    with StillElements the time corresponds to the display duration and is set 
    by the user. 

    Args:
        sequence_name
        position
        element=None
        time=None
        list_commands

    Attributes:
        id          (int): primary key of object in database
        sequence_name
        position
        time
        logic_element_id
        logic_element
        media_element_id
        media_element

    """

    __tablename__ = 'sequence_module'
    _id = Column(Integer, primary_key=True, name="id")
    _sequence_name = Column(String(50), nullable=True, name="sequence_name")
    _position = Column(Integer, name="position")
    _time = Column(Float, name="time")
    _deleted = Column(Boolean, name="deleted", default=False)
    _logic_element_id = Column(Integer,
        ForeignKey('logic_element.id'), name="logic_element_id")
    _logic_element = orm.relationship("LogicElement",
        foreign_keys=[_logic_element_id])
    _media_element_id = Column(Integer,
        ForeignKey('media_element.id'), name="media_element_id")
    _media_element = orm.relationship("MediaElement",
        foreign_keys=[_media_element_id])
    _list_commands = orm.relationship("ModuleCommand", back_populates="sequence_module", cascade="all, delete-orphan")


    def __init__(self, sequence_name, position, element=None, time=None, list_commands=[]):
        self._sequence_name = sequence_name
        self._position = position
        if isinstance(element, VideoElement):
            #get length of video
            time = element.duration
            pass
        elif isinstance(element, StillElement) \
                or isinstance(element, TextElement):
            time = time
        else:
            time = None
        self._time=time
        self._element_set(element)
        self._list_commands = list()
        self.command_add(list_commands)

    def __repr__(self):
        return "|{:04d}|{:04d}|{:<20}{}".format(self.id, self._position, self.name, self._time)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        """name is equal element name"""
        if self._media_element:
            return self._media_element.name
        else:
            return self._logic_element.name

    @property
    def sequence_name(self):
        return self._sequence_name

    @sequence_name.setter
    def sequence_name(self, name):
        self._sequence_name = name

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos

    @property
    def time(self):
        return self._time

    @property
    def media_element(self):
        return self._media_element

    @property
    def logic_element(self):
        return self._logic_element

    @property
    def list_commands(self):
        list_commands = list()
        for mc in self._list_commands:
            list_commands.append((mc.command, mc.delay))
        return list_commands

    def _element_set(self, element):
        """set element depending of class"""
        if not element:
            return
        elif issubclass(type(element), MediaElement):
            self._media_element = element
        elif issubclass(type(element), LogicElement):
            self._logic_element = element

    def element_set(self, obj):
        """add media or logic element to playlist pos"""
        if not self._media_element and not self._sequence_name:
            self._element_set(obj)
        else:
            raise Exception("SequenceModule already conatins an element.")

    def element_delete(self):
        """delete the media or logic element"""
        raise NotImplementedError

    def element_replace(self, obj):
        """replace the current media element with a new one."""
        raise NotImplementedError

    def command_add(self, command_delay_tuple):
        if not isinstance(command_delay_tuple, list):
            command_delay_tuple = [command_delay_tuple]
        for cmd in command_delay_tuple:
            if not self._command_add(cmd):
                return False
        return True

    def _command_add(self, command_delay_tuple):
        """add a command to the command list
        
            delay can be:
                > positiv: delay from start of object
                > negativ: delay before end of object
                > .9999  : delay at end of obj (send when obj is finished)
                > 0      : command send imediatly
            
            WARNING: delay will not be updtaed when element duration changes
        """

        if not isinstance(command_delay_tuple, tuple):
            command_delay_tuple = (command_delay_tuple, 0)
        tmp = ModuleCommand()
        tmp.command = command_delay_tuple[0]
        if command_delay_tuple[1] < 0:
            if self._time:
                if not command_delay_tuple[1] == -9999:
                    tmp.delay = self._time + command_delay_tuple[1]
                    if tmp.delay < 0:
                        tmp.delay = 0
                else:
                    tmp.delay = self._time
            else:
                return False  # time not set negativ value noz possible
        else:
            tmp.delay = command_delay_tuple[1]
        self._list_commands.append(tmp)
        return True

    def command_remove(self, command_obj):
        """remove a command from the command list"""
        if isinstance(command_obj, tuple):
            command_obj = command_obj[0]
        for mod_com in self._list_commands:
            if mod_com.command is command_obj:
                self._list_commands.remove(mod_com)
        #WARNING no verificartion if and which elements were deleted (or not)
        return True

    def module_delete_self(self):
        self._deleted = True

    #def rename_sequence(self, new_name):
    #    self._sequence_name = new_name

    def copy(self):
        copy = SequenceModule(
            sequence_name = self._sequence_name,
            position = self.position,
            element= self.logic_element if self.logic_element else self.media_element,
            time= self.time
        )
        for cmd in self.list_commands:
            copy.command_add(cmd)
        return copy

    @staticmethod
    def viewcontroll_placeholder():
        return SequenceModule("None", 0, element=StartElement(), time=5)


class AssosciationCommand(Base):

    __tablename__ = 'assosciation_command'
    _id = Column(Integer, primary_key=True, name="id")
    _etype = Column(String(10), name="etype")

    command_id = Column(Integer, ForeignKey('command_object.id'))
    command = orm.relationship("CommandObject")

    delay = Column(Integer)

    __mapper_args__ = {
        'polymorphic_on':_etype,
        'polymorphic_identity':'AssosciationCommand'
    }


class ModuleCommand(AssosciationCommand):
    """Assosication Table for Many to Many Relationship, with delay saved in 
    association table
    
    """

    sequence_module_id = Column(Integer, ForeignKey('sequence_module.id'))
    sequence_module = orm.relationship("SequenceModule", back_populates="_list_commands")

    __mapper_args__ = {
        'polymorphic_identity':'ModuleCommand'
    }


class EventCommand(AssosciationCommand):

    event_module_id = Column(Integer, ForeignKey('event_module.id'))
    event_module = orm.relationship("EventModule", back_populates="_list_commands")

    __mapper_args__ = {
        'polymorphic_identity':'EventCommand'
    }


class CommandObject(Base):
    """Command Database Object

    """
    __tablename__ = 'command_object'
    _id = Column(Integer, primary_key=True, name="id")
    _parents = orm.relationship("ModuleCommand", back_populates="command")
    _name = Column(String(50), name="name")
    _device = Column(String(50), name="device")
    _name_cmd = Column(String(50), name="name_cmd")
    _cmd_parameter1_str = Column(String(20), name="cmd_parameter1_str")
    _cmd_parameter2_str = Column(String(20), name="cmd_parameter2_str")
    _cmd_parameter3_str = Column(String(20), name="cmd_parameter3_str")
    _cmd_parameter1_pickled = Column(Binary(50), name="cmd_parameter1_pickled")
    _cmd_parameter2_pickled = Column(Binary(50), name="cmd_parameter2_pickled")
    _cmd_parameter3_pickled = Column(Binary(50), name="cmd_parameter3_pickled")

    def __init__(self, name, device, name_cmd, *args):
        self._name = name
        self._name_cmd = name_cmd
        self._device = device
        if args:
            self.set_parameters(*args)

    @orm.reconstructor
    def __init2__(self):
        self._cmd_parameter1 = None
        self._cmd_parameter2 = None
        self._cmd_parameter3 = None
        if self._cmd_parameter1_pickled:
            self._cmd_parameter1 = pickle.loads(self._cmd_parameter1_pickled)
        if self._cmd_parameter2_pickled:
            self._cmd_parameter2 = pickle.loads(self._cmd_parameter2_pickled)
        if self._cmd_parameter3_pickled:
            self._cmd_parameter3 = pickle.loads(self._cmd_parameter3_pickled)

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def device(self):
        return self._device

    @property
    def name_cmd(self):
        return self._name_cmd

    def get_parameters(self):
        if not self._cmd_parameter1:
            return ()
        elif self._cmd_parameter3:
            return (self._cmd_parameter1, self._cmd_parameter2,
                self._cmd_parameter3, )
        elif self._cmd_parameter2:
            return (self._cmd_parameter1, self._cmd_parameter2, )
        else:  # self.cmd_parameter1
            return (self._cmd_parameter1, )
        # Note, brackets are tuple brackets

    def set_parameters(self, *args):
        if len(args) > 0:
            self.__write_param(1, args[0])
        if len(args) > 1:
            self.__write_param(2, args[1])
        if len(args) > 2:
            self.__write_param(3, args[2])

    def __write_param(self, num, value):
        if not value:
            return None, None
        pickled = pickle.dumps(value)
        str_value = str(value)
        if num == 1:
            self._cmd_parameter1 = value
            self._cmd_parameter1_pickled = pickled
            self._cmd_parameter1_str = str_value
        elif num == 2:
            self._cmd_parameter2 = value
            self._cmd_parameter2_pickled = pickled
            self._cmd_parameter2_str = str_value
        elif num == 3:
            self._cmd_parameter3 = value
            self._cmd_parameter3_pickled = pickled
            self._cmd_parameter3_str = str_value
        else:
            raise IndexError("Only 3 parameters can be saved into db!")

    def __repr__(self):
        if self.id:
            id = self.id
        else:
            id = -1
        return "{:04d}|{}|{}|{}|{}".format(
            id, self._name, self._device, self._name_cmd, self.get_parameters())


class CommandObjectManager(ManagerBase):

    def _elements_get_with_name_from_db(self, name, num=1):
        return self._session.query(CommandObject)\
            .filter(CommandObject._name==name).first()

    def _elements_get_by_id_from_db(self, id):
        return self._session.query(CommandObject)\
            .filter(CommandObject._id==id).first()

    def _elements_get_all_from_db(self):
        return self._session.query(CommandObject).all()


class EventModule(Base):
    """Module for events of a show.
    
    No abc.ABC abstract class because of metaclass conflict
    """
    __tablename__ = 'event_module'
    _id = Column(Integer, primary_key=True, name="id")
    _sequence_name = Column(String(50), nullable=True, name="sequence_name")
    _name = Column(String(50), name="name")
    _etype = Column(String(10), name="etype")
    _list_commands = orm.relationship("EventCommand", back_populates="event_module", cascade="all, delete-orphan")
    _jump_to_target_element_id = Column(Integer, ForeignKey('logic_element.id'), name="jump_to_target_element_id", nullable=True)
    _jump_to_target_element = orm.relationship("JumpToTarget")

    __mapper_args__ = {
        'polymorphic_on':_etype,
        'polymorphic_identity':'EventModule'
    }

    def __init__(self, sequence_name, name):
        self._sequence_name = sequence_name
        self._name = name
        self._list_commands = list()

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    @property
    def sequence_name(self):
        return self._sequence_name

    @sequence_name.setter
    def sequence_name(self, name):
        self._sequence_name = name

    @property
    def list_commands(self):
        list_commands = list()
        for mc in self._list_commands:
            list_commands.append((mc.command, mc.delay))
        return list_commands

    @property
    def jump_to_target_element(self):
        return self._jump_to_target_element

    @jump_to_target_element.setter
    def jump_to_target_element(self, element):
        self._jump_to_target_element = element

    def command_add(self, command_delay_tuple):
        self._command_add(command_delay_tuple)
        return True

    def _command_add(self, command_delay_tuple):
        if not isinstance(command_delay_tuple, tuple):
            command_delay_tuple = (command_delay_tuple, 0)
        tmp = EventCommand()
        tmp.command = command_delay_tuple[0]
        if command_delay_tuple[1] < 0:
            return False
        else:
            tmp.delay = command_delay_tuple[1]
        self._list_commands.append(tmp)
        return True

    @abc.abstractmethod
    def copy(self):
        raise NotImplementedError()
        #copy = EventModule(self.sequence_name, self.name)
        #return self._copy_super_attributes(copy)

    def _copy_super_attributes(self, copy):
        for cmd in self.list_commands:
            copy.command_add(cmd)
        copy._jump_to_target_element = self._jump_to_target_element
        return copy

    @abc.abstractmethod
    def check_event(self, data):
        raise NotImplementedError()


class KeyEventModule(EventModule):

    _key_name = Column(String(50), name="key_name")
    key_event = Column(String(50), name="key_event")

    __mapper_args__ = {
        'polymorphic_identity':'KeyEvent'
    }

    def __init__(self, key, key_event, name=None, sequence_name=None):
        self.key = key
        self._key_name = key.name
        self.key_event = key_event
        if not name:
            name = "{}-{}".format(self._key_name, self.key_event)
        super().__init__(sequence_name, name)

    @orm.reconstructor
    def __load_enum(self):
        self.key = pynput.keyboard.Key[self._key_name]

    def copy(self):
        copy = KeyEventModule(
            key = self.key,
            key_event = self.key_event,
            name=self.name,
            sequence_name=self._sequence_name
        )
        return self._copy_super_attributes(copy)

    def check_event(self, data):
        if self.key == data[1]:
            if self.key_event == data[2]:
                return True
        return False


class ComEventModule(EventModule):

    _device = Column(String(50), name="device")
    _name_command = Column(String(50), name="name_command")  # get from dict
    _match_regex = Column(String(100), name="match_regex")
    _match_param1 = Column(String(20), name="_match_param1")
    _match_param2 = Column(String(20), name="_match_param2")
    _match_param3 = Column(String(20), name="_match_param3")
    _com_type = Column(Integer, name="com_type")  # to be
    # implemented

    __mapper_args__ = {
        'polymorphic_identity':'ComEvent'
    }

    def __init__(self, device, com_type, name_command, match, name=None,
                 sequence_name=None):
        self._sequence_name = None
        self._device = device
        self._com_type = com_type.value  # type ComType
        self._name_command = name_command
        if isinstance(match, list) or isinstance(match, tuple):
            self.match_parameters = match
            self._match_regex = None
        elif isinstance(match, str):
            self._match_param = None
            self._match_regex = match
        if not name:
            name = "{}-{}".format(self._device, self._name_command)
        super().__init__(sequence_name, name)

    @property
    def device(self):
        return self._device

    @property
    def com_type(self):
        return ComType(self._com_type)

    @property
    def name_command(self):
        return self._name_command

    @property
    def match_parameters(self):
        if not self._match_param1:
            return ()
        elif self._match_param3:
            return (self._match_param1, self._match_param2,
                    self._match_param3)
        elif self._match_param2:
            return (self._match_param1, self._match_param2)
        else:  # self.cmd_parameter1
            return (self._match_param1,)

    @match_parameters.setter
    def match_parameters(self, *args):  # args, tuple or list
        if len(args)==1:
            if isinstance(args[0], list) or isinstance(args[0], tuple):
                args = args[0]
        if len(args) > 0:
            self._match_param1 = args[0]
        if len(args) > 1:
            self._match_param2 = args[1]
        if len(args) > 2:
            self._match_param3 = args[2]

    def copy(self):
        copy = ComEventModule(
            device=self.device,
            com_type=self.com_type,
            name_command=self.name_command,
            match=None,
            name=self.name,
            sequence_name=self._sequence_name
        )
        copy._match_param1 = self._match_param1
        copy._match_param2 = self._match_param2
        copy._match_param3 = self._match_param3
        copy._match_regex = self._match_regex
        return self._copy_super_attributes(copy)

    def check_event(self, data):
        if data.device == self._device:
            if data.type == self.com_type:
                if data.full_answer and self.match_parameters:
                    if data.full_answer[0] == self._name_command:
                        if list(self.match_parameters) == data.full_answer[1]:
                            return True
                elif self._match_regex:
                    if re.fullmatch(self._match_regex,
                                    data.recv_answer_string):
                        return True
        return False


class ShowEvent(EventModule):

    #play, pasue, jumpnext, next_module ....

    __mapper_args__ = {
        'polymorphic_identity':'ShowEvent'
    }


class EventModuleManager(ManagerBase):

    def __init__(self, session):
        super().__init__(session)
        self._elements = self._elements_get_all_from_db()
        self.tmp_save_show_name = None

    def element_add(self, element):
        """add media element to database, if name alreadey exists append number
        to the name
        """
        self.tmp_save_show_name = element._sequence_name
        element.name = self._check_name_exists(element.name, obj=element)
        self._elements.append(element)
        self._session.add(element)
        self._session.commit()
        return True

    def _elements_load_from_db(self):
        return None

    def _elements_load_from_db_show_name(self, show_name):
        return self._session.query(EventModule)\
            .filter(EventModule._sequence_name==show_name).first()

    def _elements_get_with_name_from_db(self, name, show_name=None):
        if not show_name:
            if self.tmp_save_show_name:
                show_name = self.tmp_save_show_name
            else:
                # either show_name or tmp_save_show_name must be set
                return False
        return self._session.query(EventModule)\
            .filter(
                EventModule._sequence_name==show_name,
                EventModule._name==name
            ).first()

    def _elements_get_by_id_from_db(self, id):
        return self._session.query(EventModule)\
            .filter(EventModule._id==id).first()

    def _elements_get_all_from_db(self):
        return self._session.query(EventModule).all()


class Show():
    """SequenceObjectManager/PlaylistManager

    Manages Sequence Object. Media or LogicElements must be in the Database.
    Chanhes are commited into the database instantly. Different shows, 
    specified by their name/sequence_name can be in the same project folder 
    (reusing, media and logic elements)

    EventModules shal not be copied inside a show. They also cant be found by
    name from within the ElementManager.

    Args:
        name                                 (str): name of the show
        session (sqlalchemy.orm.Session, optional): database session, defaults
            to None. If None, s default session will be created from config 
            file.
        project_folder             (str, optional): path to a existing project
            or for a new project. only used when session is not defined. 
            Defaults to None. If None, path from config.yaml will be used. 

    Attributes:
        current_pos                (int): 
        sequence_name              (str): name of the show (sequence_name of all
            SequenceElements in sequence)
        sequence (List<SequenceElement>): Playlist list of all SequenceElements  
        session (sqlalchemy.orm.Session): database session

    """

    def __init__(self, project_folder, content_aspect_ratio='c'):
        self._show_name = None
        self._show_project_folder = os.path.expanduser(project_folder)
        self._session = Show.create_session(self._show_project_folder)
        MediaElement.set_project_path(self._show_project_folder)
        MediaElement.set_content_aspect_ratio(content_aspect_ratio)
        self._mm = MediaElementManager(self._session)
        self._lm = LogicElementManager(self._session)
        self._cm = CommandObjectManager(self._session)
        self._em = EventModuleManager(self._session)
        self._sequence = list()
        self._event_list = list()
        self._current_pos = 0
        self.show_options = ShowOptions(self._session)

    def _find_jumptotarget_elements(self):
        """find all jumptotarget_elements in playlist and set the property"""
        self.jumptotarget_elements = []
        for e in self._sequence:
            if e.logic_element:
                if isinstance(e.logic_element, JumpToTarget):
                    self.jumptotarget_elements.append(e)

    @property
    def connected_datbase(self):
        return self._session

    @property
    def show_project_folder(self):
        return self._show_project_folder

    @property
    def playlist(self):
        return sorted(self._sequence, key=lambda mod: mod.position)

    @property
    def eventlist(self):
        return sorted(self._event_list, key=lambda mod: mod._id)

    @property
    def list_media(self):
        """list all media elements saved in db (not associated with shows)"""
        return self._mm.elements

    @property
    def list_logic(self):
        """list all logic elements saved in db (not associated with shows)"""
        return self._lm.elements

    @property
    def list_jump_to_target(self):
        """as list_logic but list only jumptoelment elements"""
        return [x for x in self._lm.elements if isinstance(x, JumpToTarget)]

    @property
    def list_command(self):
        """list all command objects saved in db (not associated with shows)"""
        return self._cm.elements

    @property
    def list_event(self):
        """list all event modules saved in db from all shows 
        (associated with shows)"""
        return self._em.elements

    @property
    def module_current(self):
        """returns current element"""
        obj = self._module_get_at_pos(self._current_pos)
        if not obj:
            raise Exception("playlist at end")
        if obj.logic_element:
            if isinstance(obj.logic_element, LoopEnd):
                if obj.logic_element.counter < obj.logic_element.cycles:
                    for s in self._sequence:
                        if isinstance(s.logic_element, LoopStart) \
                            and s.logic_element.key == obj.logic_element.key:
                            self._current_pos = s.position
                            break
                    obj.logic_element.counter = obj.logic_element.counter + 1

            return self.next()
        else:
            if os.path.exists(obj.media_element.file_path):
                return obj
            else:
                self.next()
                return self.module_current

    @property
    def count(self):
        """number of modules in playlist"""
        return len(self._sequence)

    def notify(self, name_event):
        """handles events send to show"""
        self._happened_event_queue.put(name_event)

    ##### show methods #####

    @property
    def show_name(self):
        return self._show_name

    @show_name.setter
    def show_name(self, new_name):
        self._show_name = self._check_show_name_exists(new_name)

    @property
    def show_list(self):
        return self._show_load_show_names()

    def _show_load_show_names(self, deleted=False):
        r =  self._session.query(SequenceModule._sequence_name)\
            .filter(SequenceModule._deleted==deleted).distinct().all()
        return [i[0] for i in r]

    def show_new(self, name):
        if name not in self.show_list:
            self.show_close()
            if name not in self._show_load_show_names(deleted=True):
                self._show_name = name
                return True
            else:
                return False  # error code: name in waste bin
        else:
            return False  # error code: name already exists

    def show_load(self, name):
        if name in self.show_list:
            self.show_close()
            self._show_name = name
            self._module_load_from_db()
            self._event_module_load_from_db()
            self._find_jumptotarget_elements()
            self._happened_event_queue = queue.Queue()
            return True
        else:
            return False  # error code: name already exists

    def show_copy(self, name_scr_show, name_new_show):
        current_show_save = None
        if not self.show_name == name_scr_show:
            current_show_save = self.show_name
            self.show_load(name_scr_show)
        for seq_mod in self._sequence:
            if self._module_copy(seq_mod, new_show=name_new_show, positioning=False):
                continue
            else:
                self._session.rollback()
                return False
        for event_mod in self._event_list:
            if self._event_module_copy(event_mod, new_show=name_new_show):
                continue
            else:
                self._session.rollback()
                return False
        self._session.commit()
        if current_show_save:
            self.show_load(current_show_save)
        return True

    def show_rename(self, new_name, old_name=None):
        if not old_name:
            if not self._show_name:
                return False, "error code: no show loaded and no name provided"
            old_name2 = self._show_name
        else:
            if old_name in self.show_list:
                old_name2 = old_name
            else:
                return False, "error code: show does not exist"

        to_re_name = self._session.query(SequenceModule)\
            .filter(SequenceModule._sequence_name==old_name2).all()

        for mod in to_re_name:
            mod.sequece_name = new_name
        self._session.commit()

        if not old_name2:
            self.show.load(new_name)
        return True


    def show_close(self):
        self._sequence = list()
        self.show = None
        return True

    def show_delete(self, name=None):
        """delete show at database"""
        if not name:
            if not self._show_name:
                return False  # error code: no show loaded and no name provided
            del_name = self._show_name
        else:
            del_name = name

        if del_name in self.show_list:

            to_delte = self._session.query(SequenceModule)\
                .filter(SequenceModule._sequence_name==del_name).all()
            for mod in to_delte:
                mod.module_delete_self()
            self._session.commit()

            if not name:
                self.show_close()
            return True
        else:
            return False  # error code: name does not exist

    def _check_show_name_exists(self, name, num=1):
        """check if name already exists. If True, append a number if"""
        if num > 1:
            name='{}_{}'.format(name, num)
        if name in self._show_load_show_names():
            name = self._check_show_name_exists(name, num=num+1)
        return name

    ##### module methods #####

    def _module_add(self, element, pos=None, time=None, commands_delay_tuple=[]):
        """adds a module to playlist at given pos or at end when pos=None"""
        if not self._show_name:
            raise Exception("no show loaded")
        if not element.id:
            if isinstance(element, MediaElement):
                self._mm.element_add(element)
            else:
                self._lm.element_add(element)
        sm = SequenceModule(self._show_name, None,
            element=element, time=time)
        self._module_add_command(sm, commands_delay_tuple)
        return self._module_append_to_pos(sm, pos)

    def module_copy(self, pos, new_pos=None):
        module = self._module_get_at_pos(pos)
        new_mod = self._module_copy(module)
        return self._module_append_to_pos(new_mod, new_pos)

    def module_remove(self, pos):
        return self._module_remove(self._module_get_at_pos(pos))

    def module_add_still(self, name, file_path, time, **kwargs):
        """add a module coonatining a StillElement"""
        e = StillElement(name, file_path)
        return self._module_add(e, time=time, **kwargs)

    def module_add_text(self, name, text, time, **kwargs):
        """add a module coonatining a StillElement"""
        e = TextElement(name, text=text)
        return self._module_add(e, time=time, **kwargs)

    def module_text_change_text(self, pos, new_text):
        return self._module_text_change_text(self._module_get_at_pos(pos), new_text)

    def module_add_video(self, name, file_path, t_start=0, t_end=None, **kwargs):
        """add a module coonatining a StillElement"""
        e = VideoElement(name, file_path, t_start=t_start, t_end=t_end)
        return self._module_add(e, **kwargs)

    def module_add_media_by_id(self, id, time, **kwargs):
        e = self._mm._elements_get_by_id_from_db(id)
        return self._module_add(e, time=time, **kwargs)

    def module_add_jumptotarget(self, name, name_event, pos=None, **kwargs):
        """apends a jump to target sequence module"""
        jttm = JumpToTarget(name, name_event)
        ret = self._module_add(jttm, pos, **kwargs)
        self._find_jumptotarget_elements()
        return ret

    def module_add_loop(self, cycles, pos=None):
        l_start, l_end = self._lm.element_make_loop_pair(cycles)
        self._module_add(l_start, pos=pos)
        if pos:
            return self._module_add(l_end, pos=pos+1)
        else:
            return self._module_add(l_end, pos=pos)

    #def add_empty_module(self, pos=None):
    #    """add a empty module without any elements"""
    #    self.add_module(None, pos)

    #def append_empty_module(self):
    #    """add a empty module without any elements at end of sequence"""
    #    self.add_module(None)

    def module_move_up(self, pos):
        return self.module_change_position(pos, pos-1)

    def module_move_down(self, pos):
        return self.module_change_position(pos, pos+1)

    def module_change_position(self, old_pos, new_pos):
        module = self._module_get_at_pos(old_pos)
        return self._module_change_position(module, new_pos)

    def module_add_command_to_pos(self, pos, command):
        return self._module_add_command(self._module_get_at_pos(pos), command)

    def module_add_command_by_id_to_pos(self, pos, id, delay=0):
        cmd = self._cm._elements_get_by_id_from_db(id)
        return self._module_add_command(self._module_get_at_pos(pos), (cmd, delay))

    def module_remove_all_commands_from_pos(self, pos):
        module = self._module_get_at_pos(pos)
        return self._module_remove_all_commands(module)

    def event_module_add(self, event_module):
        event_module.sequence_name = self.show_name
        if self._em.element_add(event_module):
            self._event_list.append(event_module)
            return True
        return False

    def event_module_copy(self, module, new_name):
        new_mod = module.copy()
        new_mod.name = new_name
        return self.event_module_add(new_mod)

    def event_module_rename(self, module, new_name):
        return self._event_module_rename(module, new_name)

    def event_module_delete(self, module):
        return self._event_module_remove(module)

    def module_rename(self, pos, new_name):
        module = self._module_get_at_pos(pos)
        return self._module_rename(module, new_name)

    def _module_rename(self, module, new_name):
        if module.media_element:
            return self._mm.element_rename(module.media_element, new_name)
        else:
            return self._lm.element_rename(module.logic_element, new_name)
        # manager will commit

    def _event_module_rename(self, module, new_name):
        return self._em.element_rename(module, new_name)

    def _module_append_to_pos(self, module, pos=None):
        """append element at given position"""
        if not module.position:
            module.position = len(self._sequence)
        self._sequence.append(module)
        self._session.add(module)
        self._session.commit()
        if pos:
            return self._module_change_position(module, pos)
        else:
            return True

    def _module_copy(self, module, new_show=None, positioning=True):
        mod_new = module.copy()
        if new_show:
            mod_new.sequence_name = new_show
        if not positioning:
            self._session.add(mod_new)
            self._session.commit()
        else:
            mod_new.position = None
        return mod_new

    def _event_module_copy(self, module, new_name=None, new_show=None):
        new_module = module.copy()
        if new_name:
            new_module.name = new_name
        if new_show:
            new_module.sequence_name = new_show
            self._session.add(new_module)
            self._session.commit()
        return new_module

    def _module_remove(self, module):
        self._module_change_position_end(module)
        self._sequence.remove(module)
        self._session.delete(module)
        self._session.commit()
        return True

    def _event_module_remove(self, module):
        self._event_list.remove(module)
        self._session.delete(module)
        self._session.commit()
        return True

    def _module_change_position_end(self, module):
        return self._module_change_position(module, self.count-1)

    def _module_change_position(self, module, new_pos):
        """change position of sequence elements"""
        cur_pos = module.position
        if cur_pos < new_pos:
            next_pos = cur_pos+1
        elif cur_pos > new_pos:
            next_pos = cur_pos-1
        else:
            self._session.commit()
            return True

        self._module_get_at_pos(next_pos).position = cur_pos
        module.position = next_pos

        return self._module_change_position(module, new_pos)

    def _module_load_from_db(self):
        """load show from database"""
        self._sequence = self._session.query(SequenceModule).\
            filter(SequenceModule._sequence_name==self._show_name).all()

    def _event_module_load_from_db(self):
        """load show from database"""
        self._event_list = self._session.query(EventModule).\
            filter(EventModule._sequence_name==self._show_name).all()

    def _module_get_with_name(self, name):
        for seqm in self._sequence:
            if seqm.name == name:
                return seqm
        return None

    def _module_get_at_pos(self, position):
        """returns object on given playlist position"""
        if not self.show_name:
            raise Exception("no show loaded")
        elif len(self._sequence) == 0:
            raise Exception("show '{}' is empty".format(self.show_name))
        for s in self._sequence:
            if s.position == position:
                return s
        raise Exception("Position '{}' does not exist.".format(position))

    def _module_text_change_text(self, module, new_text):
        module.media_element.text = new_text
        return True

    def _module_add_command(self, module, command_delay_tuple):
        if module.command_add(command_delay_tuple):
            for cmd in module.list_commands:
                self._cm.element_add(cmd[0])
            self._session.commit()
            return True
        else:
            return False

    def _module_remove_all_commands(self, module):
        for command in module.list_commands:
            if module.command_remove(command):
                self._session.commit()
                return True
            else:
                return False

    def _handle_global_event(self, evnet_name):
        """preperation for future development
            handle a global event that must be handeled emidetly
            > e.g Blury @chapter 10 --> call event pause
        """
        #gets called by the notify function
        #compares evnet_name to global events
        #if True:
        #   signal.send("") send out new event
        #else:
        #   self.happened_event_queue.put(evnet_name)
        pass

    def next(self):
        """returns next module and handles modules with logic elements"""

        #loop through queue until empty
        while not self._happened_event_queue.empty():
            jtte = self._happened_event_queue.get()
            for e in self.jumptotarget_elements:
                if e.logic_element.id == jtte.id:
                    self._current_pos = e.position

        #increase current position and return new current element
        if self._current_pos < len(self._sequence)-1:
            self._current_pos = self._current_pos+1
            return self.module_current
        else:
            return SequenceModule.viewcontroll_placeholder()

    @staticmethod
    def create_session(project_folder, check_same_thread=False):
        """create a session and the db-file if not exist"""
        if not os.path.exists(project_folder):
            if not os.path.exists(project_folder):
                os.makedirs(project_folder)
        if check_same_thread:
            db_file = os.path.join(project_folder, 'vcproject.db3')
        else:
            db_file = os.path.join(project_folder, 'vcproject.db3') + "?check_same_thread=False"
        engine = 'sqlite:///'+db_file
        some_engine = sqlalchemy.create_engine(engine)
        Base.metadata.create_all(some_engine,
            Base.metadata.tables.values(), checkfirst=True)
        Session = orm.sessionmaker(bind=some_engine)
        return Session()