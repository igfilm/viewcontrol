import threading
import abc
import time
import logging
import queue
from enum import Enum
from blinker import signal

class ThreadCommunicationBase(threading.Thread, abc.ABC):
    """Base Class for all communication threads

    The 'run' method of the thread takes care of repeating the listening 
    process and catches connection errors (default: OSError) while other errors 
    are logged logging errors. For this only the 'listen' function has to be 
    overwritten with the device-specific communication.
    """

    __answer_queue = None
    retry_interval = 10

    def __init__(self, name, **kwargs):
        super().__init__(daemon=True, name=name, **kwargs)
        self.q_comand = queue.Queue()
        self.logger = logging.getLogger()
        self.type_exeption = (OSError)
        self.signal = signal("{}_send".format(self.name))
        self.signal.connect(self.subsr_signal_send)

    @classmethod
    def set_answer_queue(cls, answer_queue):
        cls.__answer_queue = answer_queue

    def put_queue(self, value):
        self.logger.info("<~~ recived data: '{}'".format(str(value)))
        self.__answer_queue.put(value)

    def subsr_signal_send(self, value):
        self.logger.info("~~> sending data: '{}'".format(value))
        self.q_comand.put(value)

    def run(self):
        self.logger.info("Started controll thread of device '{}'.".format(self.name))
        if not ThreadCommunicationBase.__answer_queue:
            self.logger.error("Answer Queue Not Set!")
            raise Exception("Answer Queue Not Set!")
        while True:
            try:
                self.listen()
            except self.type_exeption as ex:  #, ConnectionError, ConnectionRefusedError:
                if type(ex) is OSError:
                    self.logger.warning("{}: Communication Failed ({}). New Try in {} second(s)."
                        .format(self.name, ex.errno, 
                            ThreadCommunicationBase.retry_interval))
                else:
                    self.logger.warning("{}: Communication Failed ({}). New Try in {} second(s). Args: {}."
                        .format(self.name, type(ex), 
                            ThreadCommunicationBase.retry_interval, ex.args))
                time.sleep(ThreadCommunicationBase.retry_interval)
            except Exception as ex:
                try:
                    raise
                finally:
                    self.logger.error("Uncaught exception in process '{}'"
                            .format(self.name), exc_info=(ex))

    @abc.abstractmethod
    def listen(self):
        """The listen funtion shal manages all communication with the Device
            >listen to status masages
            >send commands at regular intervals (<100ms) from queue
            >return if command was sucsessfull
            >zuordnen von befejlen zu dict
            TODO prepare standart errors
        """
        pass

    @property
    #@abc.abstractmethod    
    def connection_active(self):
        return False


class ComPackage(object):

    def __init__(self, device, command_obj=None):
        self.device = device
        self.command_obj = command_obj
        self.send_cmd_string = None
        self.recv_answer_byte = None
        self.recv_answer_string = None
        self.type = None
        self.full_answer = None

    def __repr__(self):
        if self.full_answer:
            full_answer = self.full_answer
        else:
            full_answer = ""
        return "{} - {} - ({}) - {} {}" \
            .format(self.device, 
                self.type, 
                self.command_obj.name if self.command_obj else None,  
                self.recv_answer, 
                full_answer)

    @property
    def recv_answer(self):#
        if self.recv_answer_byte:
            return self.recv_answer_byte
        else:
            return self.recv_answer_string
    

class ComType(Enum):
    unidentifiable = 0
    success = 1
    failed = -1
    command_success = 3
    command_failed = -3
    request_success = 2
    request_failed = -2
    message_status = 42