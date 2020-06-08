import logging
import logging.config
import multiprocessing
import os
import queue
import threading

from blinker import signal

from viewcontrol.remotecontrol.threadcommunicationbase import ThreadCommunicationBase
from . import supported_devices


class ProcessCmd(multiprocessing.Process):
    def __init__(
        self,
        logger_config,
        queue_status,
        queue_comand,
        device_options,
        stop_event,
        **kwargs
    ):
        super().__init__(name="ProcessCmd", **kwargs)
        self._dummy = CommandProcess(
            logger_config,
            queue_status,
            queue_comand,
            device_options,
            self.name,
            stop_event,
        )

    def run(self):
        self._dummy.run()


class ThreadCmd(threading.Thread):
    def __init__(
        self, logger, queue_status, queue_comand, modules, stop_event, **kwargs
    ):
        super().__init__(name="ThreadCmd", **kwargs)
        self._dummy = CommandProcess(
            logger, queue_status, queue_comand, modules, self.name, stop_event
        )

    def run(self):
        self._dummy.run()


class CommandProcess:
    """Manages and starts threads of devices and handles communication.

    Args:
         logger_config (dict):
         queue_status (queue.Queue or multiprocessing.Queue):
         queue_comand (queue.Queue or multiprocessing.Queue):
         devices (dict):
         parent_name:
    """

    def __init__(
        self,
        logger_config,
        queue_status,
        queue_comand,
        devices,
        parent_name,
        stop_event,
    ):
        self.stop_event = stop_event
        self.logger_config = logger_config
        self.queue_status = queue_status
        self.queue_comand = queue_comand
        self.devices = devices
        self.name = parent_name
        self.can_run = threading.Event()
        self.can_run.set()

        self.threads = list()  # = treads
        self.signals = dict()
        self.timers = list()

        self.signal_sink = signal("sink_send")
        self.signal_sink.connect(self.subscr_signal_sink)

    def run(self):

        # must be called in run
        logging.config.dictConfig(self.logger_config)
        self.logger = logging.getLogger()

        self.logger.info("Started command_process with pid {}".format(os.getpid()))

        try:

            # TODO how will this work with different queues (and devices)
            ThreadCommunicationBase.set_answer_queue(self.queue_status)

            for name, connection in self.devices.items():
                thread_device = supported_devices.get(name)(*connection)
                self.threads.append(thread_device)
                s = signal("{}_send".format(thread_device.device_name))
                self.signals.update({thread_device.device_name: s})
                # else:
                #     self.signals.update({device.name: self.signal_sink})

            for thread in self.threads:
                thread.start()

            while not self.stop_event.is_set():
                try:
                    command_item = self.queue_comand.get(block=True, timeout=0.1)
                    logging.debug("got item")
                    self.send_to_thread(command_item)
                except queue.Empty:
                    continue
                # if isinstance(cmd_tpl, str):
                #     if cmd_tpl == "pause":
                #         [t.pause for t in self.timers]
                #     elif cmd_tpl == "resume":
                #         [t.resume for t in self.timers]
                #     elif cmd_tpl == "next":
                #         pass
                #     continue

                # if cmd_tpl[1] == 0:
                #     self.send_to_thread(cmd_tpl[0])
                # else:
                #     t = timing.RenewableTimer(
                #         cmd_tpl[1], self.send_to_thread, cmd_tpl[0]
                #     )
                #     t.start()
                #     self.timers.append(t)

            # for thread in self.threads:
            #     thread.terminate()

            self.logger.info("stop flag set. terminating processcmd")

        except Exception as e:
            try:
                raise
            finally:
                self.logger.error(
                    "Uncaught exception in process '{}'".format(self.name), exc_info=(e)
                )

    def send_to_thread(self, command_item):
        try:
            sig = self.signals.get(command_item.device)
            sig.send(command_item)
        except (KeyError, AttributeError):
            self.logger.warning(
                "Device {} not known".format(command_item.device.device_name)
            )

    def subscr_signal_sink(self, value):
        self.logger.warning(
            "~~X command '{}' was not send to {}!".format(value, value.combo_device)
        )
