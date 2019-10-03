
from wand.image import Image
from wand.color import Color
import yaml
import os
import time
import datetime
from copy import deepcopy as dc

import vctools

from sqlalchemy import orm
from sqlalchemy import Column, Integer, String, Boolean, Time, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import desc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import joinedload, selectinload

Base = declarative_base()

class Command(Base):
    __tablename__ = 'command'
    id = Column(Integer, primary_key=True)
    #parent_id = Column(Integer, ForeignKey('sequenceElements.id'))
    name = Column(String(50))
    cmd_object = Column(String(50))
    delay = Column(Integer)
    
    #@orm.reconstructor
    def __init__(self, name, cmd_object, delay=0):
        self.name = name
        self.cmd_object = cmd_object
        self.delay = delay

    def __repr__(self):
        return "{}|{}".format(self.name, self.cmd_object)

    @staticmethod
    def nocommand():
        return Command("no command", None)

class LogicElement(Base):
    __tablename__ = 'logicElement'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    position = Column(Integer)
    key = Column(Integer)
    type = Column(String(20))

    __mapper_args__ = {
        'polymorphic_on':type,
        'polymorphic_identity':'LogicElement'
    }

class LoopStart(LogicElement):
    #key = Column(Integer)
    #name = "LoopStart"

    __mapper_args__ = {
        'polymorphic_identity':'LoopStart'
    }

    def change_position(self):
        pass
        #find position of end and tellm it youre new position

class LoopEnd(LogicElement):
    #key = Column(Integer)
    #repeat = True
    #cycles = 0  # 0=inf

    __mapper_args__ = {
        'polymorphic_identity':'LoopEnd'
    }

    def change_position(self):
        pass
        #find position of end and tellm it youre new position

class LogicElementLister:

    def __init__(self, session):
        self.session = session
        self.elements = []
        self._load_elements()        

    def add_element(self, obj, num=1):
        # name=obj.name
        # if num > 1:
        #     name='{}_{}'.format(name, num)

        # res = self.session.query(LogicElement).filter(LogicElement.name==name).first()

        # if res:
        #     self.add_element(obj, num=num+1)
        #     return
        # if num > 1:
        #     obj.name=name
        self.elements.append(obj)
        self.session.add(obj)
        self.session.commit()

    def del_element(self, obj):
        pass

    def get_element_with_name(self, name):
        for e in self.elements:
            if e.name==name:
                return e
        return None

    def _load_elements(self):
        self.elements.extend(self.session.query(MediaElement).all())

    def add_element_loop(self):
        raw_key = self.session.query(LoopStart.key).order_by(desc(LoopStart.key)).first()
        if not raw_key:
            key = 1
        else:
            key = raw_key[0]
        loop_start = LoopStart()
        loop_start.key = key
        loop_start.name = "LoopStart_{}".format(loop_start.key)
        self.add_element(loop_start)
        loop_end = LoopEnd()
        loop_end.key = key
        loop_end.name = "LoopEnd_{}".format(loop_end.key)
        self.add_element(loop_end)

class MediaElement(Base):
    __tablename__ = 'mediaElement'
    id = Column(Integer, primary_key=True, )
    name = Column(String(50))
    file_path_w = Column(String(50))
    file_path_c = Column(String(50))
    type = Column(String(20))

    #parents = relationship("SequenceModule", back_populates="child")

    __mapper_args__ = {
        'polymorphic_on':type,
        'polymorphic_identity':'MediaElement'
    }
    
    #@orm.reconstructor 
    def __init__(self, name, file_path_w, file_path_c):
        self.name = name
        self.file_path_w = file_path_w
        self.file_path_c = file_path_c

    #@orm.reconstructor 
    def initialize(self, name, file_path_w, file_path_c):
        self.name = name
        self.file_path_w = file_path_w
        self.file_path_c = file_path_c

    def __repr__(self):
        return "{}|{}".format(self.name, self.file_path)

    @staticmethod
    def read_media_path_from_config():
        return vctools.read_yaml().get('media_file_path')

class VideoElement(MediaElement):

    __mapper_args__ = {
        'polymorphic_identity':'VideoElement'
    }

    #@orm.reconstructor 
    def __init__(self, name, file_path):
        super().__init__(name, file_path_w=file_path, file_path_c=None)

class StillElement(MediaElement):

    __mapper_args__ = {
        'polymorphic_identity':'StillElement'
    }

    #@orm.reconstructor
    def __init__(self, name, file_path):
        tmp_dst = os.path.join(
            MediaElement.read_media_path_from_config(), 
            str(int(time.time())) + '_' +
            os.path.splitext(os.path.basename(file_path))[0])
        tmp_dst_w = tmp_dst+ '_w.jpg'
        tmp_dst_c = tmp_dst+ '_c.jpg'
        #StillElement.insert_image(file_path, tmp_dst_w , False)
        #StillElement.insert_image(file_path, tmp_dst+ '_c.jpg', True)
        super().__init__(name, tmp_dst_w, tmp_dst_c)
    
    def __repr__(self):
        return "{}|{}|{}".format(self.name, self.file_path, self.display_time)

    @staticmethod
    def insert_image(path_scr, path_dst, cinescope=False):
        #print("cinescope: {}".format(cinescope))
        if cinescope:
            screesize =  (1920, 810)
        else:
            screesize =  (1920, 1080)
        with Image(filename=path_scr, resolution=300) as scr:
            with Image(width=1920, height=1080, background=Color("black")) as dst:   
                scr.scale(int(scr.width/scr.height*screesize[1]), screesize[1])
                offset_width = int((dst.width-scr.width)/2)
                offset_height = int((dst.height-scr.height)/2)
                dst.composite(operator='over', left=offset_width, top=offset_height, image=scr)
                dst.save(filename=path_dst)

class MediaElementLister:

    def __init__(self, session):
        self.session = session
        self.elements = []
        #self._load_elements()

    def add_element(self, obj, num=1):
        name=obj.name
        if num > 1:
            name='{}_{}'.format(name, num)

        res = self.session.query(MediaElement).filter(MediaElement.name==name).first()

        if res:
            self.add_element(obj, num=num+1)
            return
        if num > 1:
            obj.name=name
        self.elements.append(obj)
        self.session.add(obj)
        self.session.commit()

    def del_element(self, obj):
        pass

    def get_element_with_name(self, name):
        for e in self.elements:
            if e.name==name:
                return e
        return None

    def _load_elements(self):
        self.elements = self.session.query(MediaElement).all()

class SequenceModule(Base):
    __tablename__ = 'sequenceElements'
    id = Column(Integer, primary_key=True)
    sequence_name = Column(String(20), nullable=True)
    position = Column(Integer)
    time = Column(Time)
    #https://docs.sqlalchemy.org/en/13/orm/join_conditions.html
    logic_element_id = Column(Integer, ForeignKey('logicElement.id'))
    logic_element = relationship("LogicElement", foreign_keys=[logic_element_id])
    media_element_id = Column(Integer, ForeignKey('mediaElement.id'))
    media_element = relationship("MediaElement", foreign_keys=[media_element_id])
    #child = relationship("MediaElement", back_populates="parents")
    #list_commands = Column(Integer, ForeignKey('command.id'))#relationship("Command", order_by="Command.delay", uselist=True)

    def __init__(self, sequence_name, position, element=None, list_commands=Command.nocommand()):
        self.sequence_name = sequence_name
        self.position = position
        self._set_element(element)
        if isinstance(list_commands, list):
            self.list_commands = dc(list_commands)
        else:
            self.list_commands = dc([list_commands])


    def _set_element(self, element):
        if not element:
            return
        elif issubclass(type(element), MediaElement):
            self.media_element = element
        elif issubclass(type(element), LogicElement):
            self.logic_element = element

    def add_element(self, obj):
        self._set_element(obj)
    
    def del_element(self, obj):
        pass

    def replace_element(self, obj):
        #del old and add new
        pass

class Show():  #class SequenceLister()

    # def __init__(self, name, db_engine=None, *args, **kwargs):
    #     if not db_engine:
    #         project_folder = vctools.read_yaml().get('project_folder')
    #         db_file = os.path.join(project_folder, 'vcproject.db3')
    #         engine = 'sqlite:///'+db_file
    #         db_engine = create_engine(engine)
    #     self.current_pos = 0
    #     self.sequence_name = name
    #     self.db_engine = db_engine
    #     Session = sessionmaker(bind=db_engine)
    #     self.session = Session()
    #     self.sequence = []
    #     #self._load_objects_from_db()
    
    def __init__(self, session, name, *args, **kwargs):
        self.current_pos = 0
        self.sequence_name = name
        self.session = session
        self.sequence = []
        self._load_objects_from_db()

    def load_show(self):
        self.sequence = self.session.query(SequenceModule).\
            filter(SequenceModule.sequence_name==self.sequence_name, ).all()
            #join(SequenceModule, MediaElement, SequenceModule.media_element).\
            #filter(SequenceModule.sequence_name==self.sequence_name, ).all()
            #options(contains_eager(SequenceModule.media_element)).\

    def del_show(self):
        pass

    def add_module(self, element, pos=None):
        if not pos:
            pos = len(self.sequence)
        sm = SequenceModule(self.sequence_name, pos, element=element)
        self.sequence.append(sm)
        self.session.add(sm)
        self.session.commit()

    def append_module(self, element):
        self.add_module(element)
    
    def add_empty_module(self, pos=None):
        self.add_module(None, pos)

    def append_empty_module(self):
        self.add_module(None)

    def change_position(self, element, new_pos, first=True):
        cur_pos = element.position
        if cur_pos < new_pos:
            next_pos = cur_pos+1
        elif cur_pos > new_pos:
            next_pos = cur_pos-1
        else:
            self.session.commit()
            return

        self._get_object_at_pos(next_pos).position = cur_pos
        element.position = next_pos
        
        self.change_position(element, new_pos)


    def _load_objects_from_db(self):
        self.sequence = self.session.query(SequenceModule).filter(SequenceModule.sequence_name==self.sequence_name).all()

    def _get_object_at_pos(self, position):
        for s in self.sequence:
            if s.position == position:
                return s

    def first(self):
        self.current_pos = 0
        return self._get_object_at_pos(self.current_pos)

    def next(self):
        """returns next element, handles logic elements"""
        self.current_pos = self.current_pos+1
        obj =  self._get_object_at_pos(self.current_pos)
        if obj.logic_element:
            self.next()
        else:
            return obj

def create_project_databse(db_engine):
    Base.metadata.create_all(db_engine, Base.metadata.tables.values(),checkfirst=True)

if __name__ == '__main__':

    

    create = True

    project_folder = vctools.read_yaml().get('project_folder')
    db_file = os.path.join(project_folder, 'vcproject.db3')

    if create and False:
        try:
            os.remove(db_file)
        except:
            pass

    engine = 'sqlite:///'+db_file
    some_engine = create_engine(engine)
    create_project_databse(some_engine)
    Session = sessionmaker(bind=some_engine)
    session = Session()

    MediaElement('Webung Neumitglieder', "A", "B")

    elist = MediaElementLister(session)
    if create:        
        elist.add_element(StillElement('Webung Neumitglieder', '../testfiles/Werbung-neuemitglieder.pdf'))
        elist.add_element(StillElement('Flyer Winterprogram', '../testfiles/FLyerWintersem.pdf'))
        elist.add_element(StillElement('Marvel Madness', '../testfiles/MarvelMadness.pdf'))
        elist.add_element(StillElement('im moon', '../testfiles/pic1_im_moon.jpg'))
        elist.add_element(StillElement('im pda', '../testfiles/pic2_im_pda.jpg'))
        elist.add_element(StillElement('im shark', '../testfiles/pic3_im_shark.jpg'))
        elist.add_element(StillElement('psu', '../testfiles/pic4_IMG_3311.JPG'))
    elist.add_element(StillElement('name', '../testfiles/pic2_im_pda.jpg'))

    logic_loop_Start = LoopStart()
    logic_loop_Stop = LoopEnd()

    llist = LogicElementLister(session)
    llist.add_element_loop()

    show = Show(session, 'testing')
    show.add_empty_module()
    show.add_module(StillElement('Webung Neumitglieder', '../testfiles/Werbung-neuemitglieder.pdf'))
    show.add_module(llist.get_element_with_name('LoopStart_1'))
    for e in elist.elements:
        show.add_module(e)
    show.add_module(llist.get_element_with_name('LoopEnd_1'))

    #show.change_position(show.sequence[9], 5)


    playlist = Show(session, "testing")

    print("fuubar")
    