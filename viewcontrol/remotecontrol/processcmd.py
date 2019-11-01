import multiprocessing
import threading
import queue
import socket
import telnetlib
import time
import re
import importlib

import logging
import sys
import os

from blinker import signal

from viewcontrol.remotecontrol.tcpip import threadcommunication as tcpip
from viewcontrol.remotecontrol.telnet import threadcommunication as telnet
from viewcontrol.remotecontrol.threadcommunicationbase import ThreadCommunicationBase
from viewcontrol.show import CommandObject


class ProcessCmd(multiprocessing.Process):
    
    def __init__(self, logger_config, queue_status, queue_comand, device_options, **kwargs):
        super().__init__(name='ProcessCmd', **kwargs)
        self._dummy = CommandProcess(logger_config, queue_status, queue_comand, device_options, self.name)

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
            self.signals = dict()
            
            self.signal_sink = signal("sink_send")
            self.signal_sink.connect(self.subsr_signal_sink)

            for device in self.devices.values():
                if device.enabled:
                    name_tmp = device.dev_class[8:-2].split('.')
                    name_class = name_tmp.pop(-1)
                    name_module = ".".join(name_tmp)  
                    module = importlib.import_module(name_module)
                    class_ = getattr(module, name_class)
                    self.listeners.append(class_(*device.connection))
                    s = signal("{}_send".format(name_class))
                    self.signals.update({name_class: s})
                else:
                    self.signals.update({device.name: self.signal_sink})

            for l in self.listeners:
                l.start()

            while True:
                cmd_tpl = self.queue_comand.get(block=True)
                self.logger.info("~~> recived data: '{}':'{}'"
                    .format(type(cmd_tpl), str(cmd_tpl)))
                if isinstance(cmd_tpl, CommandObject):
                    pass
                elif isinstance(cmd_tpl, str):
                    # implemnt pausing and handling of delayed commands
                    if cmd_tpl == "pause":
                        pass
                    elif cmd_tpl == "resume":
                        pass
                    elif cmd_tpl == "next":
                        pass
                    continue

                try:
                    sig = self.signals.get(cmd_tpl[0].device)
                    sig.send(cmd_tpl[0])
                except (KeyError, AttributeError):
                    self.logger.warning("Device {} not known"
                        .format(cmd_tpl[0].device))

        except Exception as e:
                try:
                    raise
                finally:
                    self.logger.error("Uncaught exception in process '{}'"
                            .format(self.name), 
                        exc_info=(e))

    def subsr_signal_sink(self, value):
        self.logger.warning("Command '{}' was not send to a device!".format(value))