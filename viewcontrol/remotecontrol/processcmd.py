import multiprocessing
import threading
import queue
import socket
import telnetlib
import time
import re

import logging
import sys
import os

from blinker import signal

from viewcontrol.remotecontrol.tcpip import threadcommunication as tcpip
from viewcontrol.remotecontrol.telnet import threadcommunication as telnet
from viewcontrol.remotecontrol.threadcommunicationbase import ThreadCommunicationBase
from viewcontrol.show import CommandObject


class ProcessCmd(multiprocessing.Process):
    
    def __init__(self, logger_config, queue_status, queue_comand, modules, **kwargs):
        super().__init__(name='ProcessCmd', **kwargs)
        self._dummy = CommandProcess(logger_config, queue_status, queue_comand, modules, self.name)

    def run(self):
        self._dummy.run()

class ThreadCmd(threading.Thread):

    def __init__(self, logger, queue_status, queue_comand, modules, **kwargs):
        super().__init__(name='ThreadCmd', **kwargs)
        self._dummy = CommandProcess(logger, queue_status, queue_comand, modules, self.name)

    def run(self):
        self._dummy.run()


class CommandProcess:
    """Manages Threads for diferent devices 

    WARNING: all commands are send without any delay
    add listeners to send command events via status queue to main process
    """

    def __init__(self, logger_config, queue_status, queue_comand, devices, parent_name):
        self.logger_config = logger_config
        self.queue_status = queue_status
        self.queue_comand = queue_comand
        self.devices = devices
        self.name = parent_name
        self.can_run = threading.Event()
        self.can_run.set()


    def run(self):

        if isinstance(self.logger_config, logging.Logger):
            self.logger = self.logger_config
        else:
            logging.config.dictConfig(self.logger_config)
            self.logger = logging.getLogger()
        self.logger.info("Started command_process with pid {}".format(os.getpid()))

        try:

            self.q_recv = queue.Queue()
            self.q_stat = queue.Queue()
            ThreadCommunicationBase.set_queues(self.q_recv, self.q_stat)

            self.listeners = list()
            
            #TODO make this more dynamic
            if 'DenonDN500BD' in self.devices:
                self.listeners.append(tcpip.DenonDN500BD("192.168.178.201", 9030))
            if 'AtlonaATOMESW32' in self.devices:
                self.listeners.append(telnet.AtlonaATOMESW32("192.168.178.202", 23))

            for l in self.listeners:
                l.start()

            while True:
                cmd_obj = self.queue_comand.get(block=True)
                self.logger.info("~~> recived data: '{}':'{}'"
                    .format(type(cmd_obj), str(cmd_obj)))
                if isinstance(cmd_obj, CommandObject):
                    pass
                elif isinstance(cmd_obj, str):
                    # implemnt pausing and handling of delayed commands
                    if cmd_obj == "pause":
                        pass
                    elif cmd_obj == "resume":
                        pass
                    elif cmd_obj == "next":
                        pass
                    continue

                #maybe automate by cheking all regigisstered event names
                if cmd_obj.device == "DenonDN500BD":
                    signal("DenonDN500BD_send").send(cmd_obj)
                if cmd_obj.device == "AtlonaATOMESW32":
                    signal("AtlonaATOMESW32_send").send(cmd_obj)

        except Exception as e:
                try:
                    raise
                finally:
                    self.logger.error("Uncaught exception in process '{}'"
                            .format(self.name), 
                        exc_info=(e))