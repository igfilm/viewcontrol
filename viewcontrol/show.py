import yaml
import os
import time
import datetime
from copy import deepcopy as dc
from numpy import array, arange
import math
from shutil import copyfile
import queue

from sqlalchemy import orm
from sqlalchemy import Column, Integer, String, Boolean, Time, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import joinedload, selectinload

from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.resize import resize

from wand.image import Image
from wand.color import Color
from wand.drawing import Drawing


Base = declarative_base()

def create_project_databse(db_engine):
    Base.metadata.create_all(db_engine, Base.metadata.tables.values(),checkfirst=True)

def create_session(project_folder):
    if not os.path.exists(project_folder):
        if not os.path.exists(project_folder):
            os.makedirs(project_folder)
    db_file = os.path.join(project_folder, 'vcproject.db3')
    engine = 'sqlite:///'+db_file
    some_engine = create_engine(engine)
    create_project_databse(some_engine)
    Session = sessionmaker(bind=some_engine)
    return Session()


class Command(Base):
    """Command Database Object

    """
    __tablename__ = 'command'
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('sequenceElements.id'))
    parent = relationship("SequenceModule", back_populates="_list_commands")
    name = Column(String(50))
    device = Column(String(50))
    name_cmd = Column(String(50))
    cmd_parameter1 = Column(String(10))
    cmd_parameter2 = Column(String(10))
    cmd_parameter3 = Column(String(10))
    delay = Column(Integer)
    session = None
    #can be extendet with expected values to check for errors
    
    @classmethod
    def set_session(cls, session):
        cls.session = session

    def __init__(self, name, device, name_cmd, *args, delay=0):
        self.name = name
        self.name_cmd = name_cmd
        self.device = device
        self.delay = delay
        self.set_parameters(*args)
        self._update_db()

    def get_args(self):
        if not self.cmd_parameter1:
            return ()
        elif self.cmd_parameter3:
            return (int(self.cmd_parameter1), int(self.cmd_parameter2), int(self.cmd_parameter3))
        elif self.cmd_parameter2:
            return (int(self.cmd_parameter1), int(self.cmd_parameter2))
        else:  # self.cmd_parameter1
            return (int(self.cmd_parameter1),)

    def set_parameters(self, *args):
        if len(args) > 0:
            self.cmd_parameter1 = args[0]
        if len(args) > 1:
            self.cmd_parameter2 = args[1]
        if len(args) > 2:
            self.cmd_parameter3 = args[2]

    def _update_db(self):
        #return
        if not Command.session:
            return
        if not self.id:
            Command.session.add(self)
        Command.session.commit()

    def __repr__(self):
        return "{}|{}|{}|{}".format(self.name, self.device, self.name_cmd, self.get_args())


class LogicElement(Base):
    """Base class for Logic Elements.
    
    Args:
        name (str): name of the logic element
        key  (int): unique key of logic element (important for loops)

    Attributes:
        name    (str): name of the logic element
        key     (int): unique key of logic element (important for loops)
        id      (int): primary key of object in database
        etyp (string): polymorphic_identity of element in database

    """
    __tablename__ = 'logicElement'
    id = Column(Integer, primary_key=True)
    _name = Column(String(50), name="name", unique=True)
    _key = Column(Integer, name="key")
    _etype = Column(String(20), name="etype")

    __mapper_args__ = {
        'polymorphic_on':_etype,
        'polymorphic_identity':'LogicElement'
    }

    def __init__(self, name, key):
        self.name = name
        self._key = key

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


class LogicElementManager:
    """Manager for all lofic elemets at runtime and in database.

    Args:
        session (sqlalchemy.orm.Session): database session

    Attributes:
        session  (sqlalchemy.orm.Session): database session
        elements     (Lits<MediaElemets>): list of active logic elemets

    """

    def __init__(self, session):
        self._session = session
        self._elements = []
        self._elements_load_from_db()

    @property
    def session(self):
        return self._session

    @property
    def elements(self):
        return self._elements

    def element_add(self, element, num=1):
        element.name = self._check_name_exists(element.name)
        self._elements.append(element)
        self.session.add(element)
        self.session.commit()
        return True

    def element_delete(self, element):
        return False

    def element_rename(self, element, new_name):
        element.name = self._check_name_exists(new_name)
        self._session.commit()
        return True

    def element_make_loop_pair(self, cycles):
        """make a pair of loop elements 
        which will be added to the list via add_element by the calling function
        """
        raw_key = self.session.query(LoopStart._key).order_by(desc(LoopStart._key)).first()
        if not raw_key:
            key = 1
        else:
            key = raw_key[0]
        loop_start = LoopStart("LoopStart_{}".format(key), key)
        loop_end = LoopEnd("LoopEnd_{}".format(key), key, cycles)
        return loop_start, loop_end

    def element_get_with_name(self, name):
        for e in self.elements:
            if e.name==name:
                return e
        return None

    def _elements_load_from_db(self):
        self.elements.extend(self.session.query(MediaElement).all())    

    def _check_name_exists(self, name, num=1):
        if num > 1:
            name='{}_{}'.format(name, num)
        name_exists = self.session.query(MediaElement).filter(LogicElement._name==name).first()
        if name_exists:
            name = self._check_name_exists(name, num=num+1)
        return name


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
    __tablename__ = 'mediaElement'
    id = Column(Integer, primary_key=True, )
    _name = Column(String(20), name ="name", unique=True)
    _file_path_w = Column(String(200), name="file_path_w", unique=True)
    _file_path_c = Column(String(200), name="file_path_c", unique=True)
    _etype = Column(String(10), name="etype")

    __mapper_args__ = {
        'polymorphic_on':_etype,
        'polymorphic_identity':'MediaElement'
    }

    project_path = None
    content_aspect_ratio = 'widescreen'

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
    def file_path(self):
        if MediaElement.content_aspect_ratio == 'widescreen':
            return os.path.join(MediaElement.project_path, self._file_path_w)
        else:
            return os.path.join(MediaElement.project_path, self._file_path_c)
    
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    def __init__(self, name, file_path_w, file_path_c):
        self._name = name
        self._file_path_w = file_path_w
        self._file_path_c = file_path_c

    def __repr__(self):
        return "{}|{}".format(type(self), self.name)


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
        
        adst_c, rdst_c = MediaElement._create_abs_filepath(file_path, "_c", ".mp4")
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
            adst_w, rdst_w = MediaElement._create_abs_filepath(file_path, "_w", ".mp4")
            self._insert_video(file_path, adst_w, 
                content_aspect=content_aspect_ratio, 
                cinescope=False, 
                t_start=t_start, 
                t_end=t_end)
        super().__init__(name, rdst_w, rdst_c)

    @property
    def duration(self):
        return self._duration

    def _insert_video(self, path_scr, path_dst, content_aspect=None, cinescope=True, t_start=0, t_end=None):
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
    def _make_text_image(text, save_path):
        with Drawing() as draw:
            with Image(width=1920, height=1080, background=Color("black")) as image:
                #draw.font = 'wandtests/assets/League_Gothic.otf'
                draw.font_size = 100
                draw.stroke_color = "white"
                draw.fill_color = "white"
                draw.text_alignment = 'center'
                draw.text(int(image.width / 2), int(image.height / 2), text)
                draw(image)
                image.save(filename=save_path) 


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

        if cinescope:
            screesize =  (1920, 810)
        else:
            screesize =  (1920, 1080)

        max_upscale = 2

        with Image(filename=path_scr) as scr:
            scr.colorspace = 'rgb'
            scr.format = 'jpeg'            
            a = screesize[0]/scr.width
            b = screesize[1]/scr.height
            scale = min(a, b)
            if max_upscale and scale > max_upscale:
                scale = max_upscale 
            s_size = (int(scr.width * scale), int(scr.height * scale))

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


class MediaElementManager:
    """Manager for all media elemets at runtime and in database.

    Args:
        session (sqlalchemy.orm.Session): database session

    Attributes:
        session  (sqlalchemy.orm.Session): database session
        elements     (Lits<MediaElemets>): list of active media elemets

    """

    def __init__(self, session):
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
        """add media element to database, if name alreadey exists append number
        to the name
        """
        element.name = self._check_name_exists(element.name)
        self._elements.append(element)
        self._session.add(element)
        self._session.commit()
        return True

    def element_delete(self, element):
        return False

    def element_rename(self, element, new_name):
        element.name = self._check_name_exists(new_name)
        self._session.commit()
        return True

    def element_get_with_name(self, name):
        for e in self._elements:
            if e.name==name:
                return e
        return None

    def _check_name_exists(self, name, num=1):
        if num > 1:
            name='{}_{}'.format(name, num)
        name_exists = self._session.query(MediaElement).filter(MediaElement._name==name).first()
        if name_exists:
            name = self._check_name_exists(name, num=num+1)
        return name

    def _elements_load_from_db(self):
        self._elements = self._session.query(MediaElement).all()


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
    
    __tablename__ = 'sequenceElements'
    id = Column(Integer, primary_key=True)
    sequence_name = Column(String(20), nullable=True)
    position = Column(Integer)
    time = Column(Float)
    _deleted = Column(Boolean, name="deleted", default=False)
    #https://docs.sqlalchemy.org/en/13/orm/join_conditions.html
    _logic_element_id = Column(Integer, 
        ForeignKey('logicElement.id'), name="logic_element_id")
    logic_element = relationship("LogicElement", 
        foreign_keys=[_logic_element_id])
    _media_element_id = Column(Integer, 
        ForeignKey('mediaElement.id'), name="media_element_id")
    media_element = relationship("MediaElement", 
        foreign_keys=[_media_element_id])
    _list_commands = relationship("Command", back_populates="parent")


    def __init__(self, sequence_name, position, element=None, time=None, list_commands=[]):
        self.sequence_name = sequence_name
        self.position = position
        if isinstance(element, VideoElement):
            #get length of video
            time = element.duration
            pass
        elif isinstance(element, StillElement) \
                or isinstance(element, TextElement):
            time = time
        else:
            time = None
        self.time=time
        self._element_set(element)
        if isinstance(list_commands, list):
            self._list_commands = list_commands
        else:
            self._list_commands = [list_commands]

    def __repr__(self):
        return "|{:04d}|{:<20}{}".format(self.position, self.name, self.time)

    @property
    def name(self):
        """name is equal element name"""
        if self.media_element:
            return self.media_element.name
        else:
            return self.logic_element.name

    @property
    def list_commands(self):
        return self._list_commands

    def _element_set(self, element):
        """set element depending of class"""
        if not element:
            return
        elif issubclass(type(element), MediaElement):
            self.media_element = element
        elif issubclass(type(element), LogicElement):
            self.logic_element = element

    def element_add(self, obj):
        """add media or logic element to playlist pos"""
        if not self.media_element and not self.sequence_name:
            self._element_set(obj)
        else:
            raise Exception("SequenceModule already conatins an element.")

    def element_delete(self):
        """delete the media or logic element"""
        raise NotImplementedError

    def element_replace(self, obj):
        """replace the current media element with a new one."""
        raise NotImplementedError

    def command_add(self, command_obj):
        """add a command to the command list"""
        self._list_commands.append(command_obj)

    def command_remove(self, command):
        """remove a command from the command list"""
        raise NotImplementedError

    def module_delete_self(self):
        self._deleted = True

    @staticmethod
    def viewcontroll_placeholder():
        return SequenceModule("None", 0, element=StartElement(), time=5)


class Show():
    """SequenceObjectManager/PlaylistManager

    Manages Sequence Object. Media or LogicElements must be in the Database.
    Chanhes are commited into the database instantly. Different shows, 
    specified by their name/sequence_name can be in the same project folder 
    (reusing, media and logic elements)

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
        sequence_name              (str): name of the show (sequece_name of all
            SequenceElements in sequence)
        sequence (List<SequenceElement>): Playlist list of all SequenceElements  
        session (sqlalchemy.orm.Session): database session

    """
    
    def __init__(self, project_folder, content_aspect_ratio='c'):
        self._show_name = None
        self._show_project_folder = os.path.expanduser(project_folder) 
        self._session = create_session(self._show_project_folder)
        MediaElement.set_project_path(self._show_project_folder)
        MediaElement.set_content_aspect_ratio(content_aspect_ratio)
        self._mm = MediaElementManager(self._session)
        self._lm = LogicElementManager(self._session)
        self._sequence = list()  
        self._current_pos = 0 

    def _find_jumptotarget_elements(self):
        """find all jumptotarget_elements in playlist and set the property"""
        self.jumptotarget_elements = []
        for e in self._sequence:
            if e.logic_element:
                if isinstance(e.logic_element, JumpToTarget):
                    self.jumptotarget_elements.append(e)

    @property
    def show_project_folder(self):
        return self._show_project_folder

    @property
    def playlist(self):
        return sorted(self._sequence, key=lambda mod: mod.position)

    @property
    def media_list(self):
        return self._mm.elements

    @property
    def logic_list(self):
        return self._lm.elements

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

    @property
    def show_list(self):
        return self._show_load_show_names()

    def _show_load_show_names(self, deleted=False):
        r =  self._session.query(SequenceModule.sequence_name)\
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
            self._find_jumptotarget_elements()
            self._happened_event_queue = queue.Queue()
            return True
        else:
            return False  # error code: name already exists

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
                .filter(SequenceModule.sequence_name==del_name).all()
            for mod in to_delte:
                mod.module_delete_self()
            self._session.commit()

            if not name:
                self.show_close()
            return True
        else:
            return False  # error code: name does not exist
        
        
    ##### module methods #####
    
    def _module_add(self, element, pos=None, time=None, commands=[]):
        """adds a module to playlist at given pos or at end when pos=None"""
        if not self._show_name:
            raise Exception("no show loaded")
        if isinstance(element, MediaElement):
            self._mm.element_add(element)
        else:
            self._lm.element_add(element)
        sm = SequenceModule(self._show_name, len(self._sequence), 
            element=element, time=time, list_commands=commands)
        return self._module_append_to_pos(sm, pos)

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

    def _module_text_change_text(self, module, new_text):
        module.media_element.text = new_text
        return True

    def module_add_video(self, name, file_path, t_start=0, t_end=None, **kwargs):
        """add a module coonatining a StillElement"""
        e = VideoElement(name, file_path, t_start=t_start, t_end=t_end)
        return self._module_add(e, **kwargs)

    def module_add_jumptotarget(self, name, name_event, pos=None, commands=[]):
        """apends a jump to target sequence module"""
        jttm = JumpToTarget(name, name_event)
        ret = self._module_add(jttm, pos, commands=commands)
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
        element = self._module_get_at_pos(old_pos)
        return self._module_change_position(element, new_pos)

    def module_add_command_to_pos(self, pos, command):
        return self._module_add_command(self._module_get_at_pos(pos), command)

    def module_rename(self, pos, new_name):
        element = self._module_get_at_pos(pos)
        return self._module_rename(element, new_name)

    def _module_rename(self, module, new_name):
        if module.media_element:
            return self._mm.element_rename(module.media_element, new_name)
        else:
            return self._lm.element_rename(module.logic_element, new_name)
        # manager will commit

    def _module_append_to_pos(self, element, pos=None):
        """append element at given position"""
        self._sequence.append(element)
        self._session.add(element)
        self._session.commit()
        if pos:
            return self._module_change_position(element, pos)
        else:
            return True

    def _module_remove(self, element):
        self._module_change_position_end(element)
        self._sequence.remove(element)
        self._session.delete(element)
        self._session.commit()
        return True

    def _module_change_position_end(self, element):
        return self._module_change_position(element, self.count-1)

    def _module_change_position(self, element, new_pos):
        """change position of sequence elements"""
        cur_pos = element.position
        if cur_pos < new_pos:
            next_pos = cur_pos+1
        elif cur_pos > new_pos:
            next_pos = cur_pos-1
        else:
            self._session.commit()
            return True

        self._module_get_at_pos(next_pos).position = cur_pos
        element.position = next_pos
        
        return self._module_change_position(element, new_pos)

    def _module_load_from_db(self):
        """load show from database"""
        self._sequence = self._session.query(SequenceModule).\
            filter(SequenceModule.sequence_name==self._show_name).all()

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
    
    def _module_add_command(self, element, command):
        if not isinstance(command, list):
            command = [command]
        for cmd in command:
            element.command_add(cmd)
        self._session.commit()
        return True


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
            event = self._happened_event_queue.get()
            for e in self.jumptotarget_elements:
                if e.logic_element.name_event in event:
                    self._current_pos = e.position

        #increase current position and return new current element
        if self._current_pos < len(self._sequence)-1:
            self._current_pos = self._current_pos+1
            return self.module_current
        else:
            return SequenceModule.viewcontroll_placeholder()