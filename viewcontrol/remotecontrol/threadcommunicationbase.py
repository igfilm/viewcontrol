import threading
import abc
import time
import logging
import queue
from blinker import signal

class ThreadCommunicationBase(threading.Thread, abc.ABC):
    """Base Class for all communication threads

    The 'run' method of the thread takes care of repeating the listening 
    process and catches connection errors (default: OSError) while other errors 
    are logged logging errors. For this only the 'listen' function has to be 
    overwritten with the device-specific communication.
    """

    __q_recv = None
    __q_stat = None
    retry_interval = 10
    #logger as classs variable?

    def __init__(self, name, type_exeption=(OSError), **kwargs):
        super().__init__(daemon=True, name=name, **kwargs)
        self.q_send = queue.Queue()
        self.logger = logging.getLogger()
        self.type_exeption = type_exeption
        self.signal = signal("{}_send".format(self.name))
        self.signal.connect(self.subsr_signal_send)

    @classmethod
    def set_queues(cls, q_recv ,q_stat):
        cls.__q_recv = q_recv
        cls.__q_stat = q_stat

    def put_q_recv(self, value):
        self.logger.info("<~~ send data recv: '{}'".format(value))
        self.__q_recv.put(value)

    def put_q_stat(self, value):
        self.logger.info("<~~ send data stat: '{}'".format(value))
        self.__q_stat.put(value)

    def subsr_signal_send(self, value):
        self.q_send.put(value)

    def run(self):
        self.logger.info("Started controll thread of device '{}'.".format(self.name))
        if not (ThreadCommunicationBase.__q_recv
                 and ThreadCommunicationBase.__q_stat):
            self.logger.error("One or many Queues not set!")
            raise Exception("One or many Queues not set!")
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
        pass