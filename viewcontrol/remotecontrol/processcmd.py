import logging
import logging.config
import multiprocessing
import os
import queue
import threading

from blinker import signal

from . import supported_devices
from .threadcommunicationbase import ThreadCommunicationBase
from ..util import timing


class ProcessCmd(multiprocessing.Process):
    """Dummy starting ThreadCmd as process. See ThreadCmd for args."""

    def __init__(
        self,
        queue_status,
        queue_command,
        device_options,
        stop_event,
        logger_config,
        **kwargs,
    ):
        super().__init__(name="ProcessCmd", **kwargs)
        self._dummy = CommandProcess(
            queue_status,
            queue_command,
            device_options,
            self.name,
            stop_event,
            logger_config=logger_config,
        )

    def run(self):
        """Method to be run in sub-process; runs CommandProcess.run();"""
        self._dummy.run()


class ThreadCmd(threading.Thread):
    """Dummy to starting ThreadCmd as thread. See ThreadCmd for args."""

    def __init__(self, queue_status, queue_command, modules, stop_event, **kwargs):
        super().__init__(name="ThreadCmd", **kwargs)
        self._dummy = CommandProcess(
            queue_status,
            queue_command,
            modules,
            self.name,
            stop_event,
            logger_config=None,
        )

    def run(self):
        """Method representing the thread’s activity. Runs CommandProcess.run()"""
        self._dummy.run()


class CommandProcess:
    """Manages and starts threads of devices and handles communication.

    Args:
         queue_status (queue.Queue or multiprocessing.Queue): queue over which
            received messages will be returned from process.
         queue_command (queue.Queue or multiprocessing.Queue): queue over which
            commands will be passed to process.
         devices (dict): dict of device_name:connection telling the thread/process
            which device threads to start and which which ip and port.
            E.g.: {Behringer X32: (192.168.178.22, 10023)}
         name_thread (str): name of thread ot process.
         stop_event (threading.Event or multiprocessing.Event): Event object which
            will stop thread when set.
         logger_config (dict or None): pass a queue logger logger config (only when
            using multiprocessing). Default to None.

    """

    def __init__(
        self,
        queue_status,
        queue_command,
        devices,
        name_thread,
        stop_event,
        logger_config=None,
    ):
        self.stop_event = stop_event
        self.logger_config = logger_config
        self.queue_status = queue_status
        self.queue_command = queue_command
        self.devices = devices
        self.name = name_thread
        self.can_run = threading.Event()
        self.can_run.set()

        self.threads = list()  # = treads
        self.signals = dict()
        self.timers = list()

        self.signal_sink = signal("sink_send")
        self.signal_sink.connect(self._subscr_signal_sink)

        self.logger = None

    def run(self):
        """Run function for thread/process, to be called by dummies."""

        # must be called in run
        if self.logger_config:
            logging.config.dictConfig(self.logger_config)
        self.logger = logging.getLogger()

        self.logger.info("Started command_process with pid {}".format(os.getpid()))

        try:

            ThreadCommunicationBase.set_answer_queue(self.queue_status)

            stop_event = threading.Event()
            for name, connection in self.devices.items():
                thread_device = supported_devices.get(name)(
                    *connection, stop_event=stop_event
                )
                self.threads.append(thread_device)
                s = signal("{}_send".format(thread_device.device_name))
                self.signals.update({thread_device.device_name: s})

            others = [d for d in list(supported_devices) if d not in list(self.devices)]
            for device in others:
                self.signals.update({device: self.signal_sink})

            for thread in self.threads:
                thread.start()

            while not self.stop_event.is_set():
                try:
                    command_item = self.queue_command.get(block=True, timeout=0.1)
                    logging.debug("got item")

                    if isinstance(command_item, str):
                        # command item is a command to pause/resume the delay timers
                        if command_item == "pause":
                            [t.pause() for t in self.timers]
                        elif command_item == "resume":
                            [t.resume() for t in self.timers]
                        elif command_item == "next":
                            pass
                        continue
                    else:
                        # command item is a actual CommandItem
                        if command_item.delay == 0:
                            self._send_to_thread(command_item)
                        else:
                            t = timing.PausableTimer(
                                command_item.delay, self._send_to_thread, command_item
                            )
                            t.start()
                            self.timers.append(t)

                except queue.Empty:
                    continue

            self.logger.info("stop flag set. stopping timers ...")
            [t.cancel() for t in self.timers]

            stop_event.set()
            self.logger.info("stop flag set. stopping threads ...")

            count = -1
            while count < len(self.threads):
                count = 0
                for thread in self.threads:
                    if thread.is_alive():
                        thread.join(timeout=0.01)
                    else:
                        count += 1

            self.logger.info("stop flag set. terminated processcmd")

        except Exception as e:
            try:
                raise
            finally:
                self.logger.error(
                    "Uncaught exception in process '{}'".format(self.name), exc_info=e
                )

    def _send_to_thread(self, command_item):
        """send command item to thread via a blinker signal

        Args:
            command_item(CommandItem)

        """
        try:
            sig = self.signals.get(command_item.device)
            sig.send(command_item)
        except (KeyError, AttributeError):
            self.logger.warning(
                "Device {} not known".format(command_item.device.device_name)
            )

    def _subscr_signal_sink(self, command_item):
        """subscriber for all signals for which device no thread was started.

        Its only job to print a warning in the log that device is not started.

        Args:
            command_item(CommandItem)

        """
        self.logger.warning(
            f"~~X Device '{command_item.device}' not started, command was not send!"
        )
