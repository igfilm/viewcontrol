import abc
import logging
import os
import queue
import threading
import warnings
from enum import Enum

from blinker import signal

from . import dict_command_folder
from .commanditem import CommandTemplateList


class DeviceType(Enum):
    undefined = 0
    audio = 10
    video = 20
    light = 30
    other = 90


class ThreadCommunicationBase(threading.Thread, abc.ABC):
    """Base Class for all communication threads

    The 'run' method of the thread takes care of repeating the listening
    process and catches connection errors (default: OSError) while other errors
    are logged logging errors. For this only the 'listen' function has to be
    overwritten with the device-specific communication.

    While data to send is received via a signal event send via blinker with the name
    of the device as in device_name, Answer and Event messages are put into a queue
    provided by the main task.

    TODO: write metaclass to have __answer_queue as class property

    Args:
        name (str): name of the thread.
        stop_event (threading.Event or multiprocessing.Event): see Attributes
        **kwargs: Arbitrary keyword arguments passed to parent (``threading.Thread``).

    Attributes:
        retry_interval(int): time in seconds between (re)connection attempts to devices.
        stop_event (threading.Event or multiprocessing.Event): when set stops this
            process and all device threads by asking nicely.
        signal (blinker.Signal): Signal instance where command has to be send to.
        type_exception (type or tuple of type): Exceptions which are caused by
            connection errors with device. For different handling. Defaults to OSError.
        dict_command_template (commanditem.CommandTemplateList): dictionary containing
            all supported commands of class.
        dict_command_template_path (pathlib.path): path to file dict_command_template
            was loaded from.

    """

    __answer_queue = None
    retry_interval = 10

    device_name = __qualname__
    """str: name reference of device. To be overwritten with device names."""

    device_type = DeviceType.undefined
    """DeviceType: device category/type"""

    dict_command_template = None
    dict_command_template_path = None

    daemon = True

    @classmethod
    def update_dict_command_template(cls):
        module = cls.__module__
        # tmp_mod_name = pathlib.Path(module)
        tmp_mod_name = module.split(".")[-1]
        tmp_path = dict_command_folder.joinpath(tmp_mod_name).with_suffix(".yaml")
        if tmp_path.exists():
            cls.dict_command_template_path = tmp_path
            cls.dict_command_template = CommandTemplateList(tmp_path)
            cls.dict_command_template.load_objects_from_yaml()

    def __init__(self, name, stop_event=None, **kwargs):
        if not stop_event:
            stop_event = threading.Event()
            daemon = True
        else:
            daemon = False
        super().__init__(daemon=daemon, name=name, **kwargs)
        self.stop_event = stop_event
        self._queue_command = queue.Queue()
        self.logger = logging.getLogger(self.name)
        self.type_exception = OSError
        self.signal = signal("{}_send".format(self.name))
        self.signal.connect(self._put_into_command_queue)
        self.dict_command_template = None
        self.dict_command_template_path = None
        tmp_mod_name = self.__module__.split(".")[-1]
        tmp_path = dict_command_folder.joinpath(tmp_mod_name).with_suffix(".yaml")
        if tmp_path.exists():
            self.dict_command_template_path = tmp_path
            self.dict_command_template = CommandTemplateList(tmp_path)
            self.dict_command_template.load_objects_from_yaml()
            self.dict_command_template.is_valid()

    @classmethod
    def set_answer_queue(cls, answer_queue):
        """Sets the queue, received answers are put in.

        Args:
            answer_queue (multiprocessing.Queue or queue.Queue): Queue object over which
                all received messages are past to a handling function.

        """
        cls.__answer_queue = answer_queue

    def _put_into_answer_queue(self, obj):
        """To be called by subprocess for putting messages into answer queue.

        This way all received messages (or better there string representation) will be
        logged.

        Args:
            obj (object or ComPackage): obj to be put in queue, should usually be a
                ComPackage object.

        """
        self.logger.info("<~~ received data: '{}'".format(str(obj)))
        self.__answer_queue.put(obj)

    def _put_into_command_queue(self, command_send_item, comment=""):
        """proxy collecting all events (send requests) for this device

        Args:
            command_send_item (CommandSendItem):

        """
        if comment:
            comment = "  # " + comment
        self.logger.info("~~> sending data: '{}'{}".format(command_send_item, comment))
        self._queue_command.put(command_send_item)

    def run(self):
        """Method representing the thread’s activity.

        Don't overwrite this method but ``listen()`` for any Protocol/Device specific
        code.

        """
        # self.logger = logging.getLogger(self.name)
        self.logger.info(
            "Started control thread of device '{}' with pid {}.".format(
                self.name, os.getpid()
            )
        )
        if not ThreadCommunicationBase.__answer_queue:
            self.logger.error("Answer Queue Not Set!")
            raise Exception("Answer Queue Not Set!")

        self._on_enter()
        while not self.stop_event.is_set():
            try:
                self._main()
            except self.type_exception as ex:
                if type(ex) is OSError:
                    self.logger.warning(
                        "{}: Communication Failed ({}). "
                        "New Try in {} second(s).".format(
                            self.name, ex.errno, ThreadCommunicationBase.retry_interval,
                        )
                    )
                else:
                    self.logger.error(
                        "{}: Communication Failed ({}). "
                        "New Try in {} second(s). Args: {}.".format(
                            self.name,
                            type(ex),
                            ThreadCommunicationBase.retry_interval,
                            ex.args,
                        )
                    )
                # like sleep, but can be stopped by the stop event
                self.stop_event.wait(ThreadCommunicationBase.retry_interval)
            except Exception as ex:
                try:
                    raise
                finally:
                    self.logger.error(
                        "Uncaught exception in process '{}'".format(self.name),
                        exc_info=ex,
                    )

        self._on_exit()

    @abc.abstractmethod
    def _main(self):
        """This method is the equivalent to the Thread().run() method and

        contains any protocol/device specific code. This includes:

            - sending messages/commands
            - Receive responses, events and status messages
            - possibly return whether messages have been received and commands accepted

        """
        pass

    def _compose(self, command_item):
        """Blueprint to compose a massage, this implementation should fit most needs.

        Args:
            command_item (CommandSendItem):

        """

        try:
            command_template = self.dict_command_template.get(command_item.command)
            if command_item.request:
                str_formatter = command_template.request_object
            else:
                str_formatter = command_template.command_composition

            if isinstance(command_item.arguments, dict):
                arguments = command_template.sorted_tuple_from_dict(
                    command_item.arguments
                )
            else:
                arguments = command_item.arguments

            str_composed = str_formatter.format(*arguments)
            self.logger.debug(f"Composed String: {str_composed}")
            return str_composed

        except TypeError as ex:
            self.logger.warning(
                f"error composing message {command_item}. Error Message: {ex}"
            )
            return None

    def _analyse(self, *args):
        """Function should be used to analyze code to have a common structure.

        Args:
            *args: arguments, depending on protocol.

        """
        NotImplementedError("please overwrite in subclass")

    def _on_enter(self):
        """Called before entering the main loop, to be overwritten in sub class, or not.

        Call super method to maintain consitent logging, when overwriting.

        """
        self.logger.debug("entering main loop")

    def _on_exit(self):
        """Called after leaving the main loop, to be overwritten in sub class, or not.

        Call super method to maintain consitent logging, when overwriting.

        """
        self.logger.debug("exiting main loop")


class ComPackage(object):
    """

    Args:
        device:
        command_obj:

    Attributes:
        device:
        command_obj: that was send

    """

    warnings.warn("obj will be removed", DeprecationWarning, stacklevel=2)

    def __init__(self, device, command_obj=None):
        """

        Args:
            device:
            command_obj:

        """
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
        return "{} - {} - ({}) - {} {}".format(
            self.device,
            self.type,
            "placeholder",
            # self.command_obj.name if self.command_obj else None,
            self.recv_answer,
            full_answer,
        )

    @property
    def recv_answer(self):  #
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
