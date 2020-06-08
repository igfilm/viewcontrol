import re

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from viewcontrol.remotecontrol.threadcommunicationbase import (
    ThreadCommunicationBase,
    ComType,
)
from ..commanditembase import CommandItem, CommandAnswerItem, format_arg_count


class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all OSC communication

    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command string out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both are meant to be overwritten to adjust the for new devices

    """

    def __init__(self, target_ip, target_port):
        # target_ip, target_port are a typical config file variable
        self.target_ip = target_ip
        self.target_port = target_port
        self.dispatcher = Dispatcher()
        self.dispatcher.set_default_handler(self._analyse)
        self.last_composed = None
        super().__init__(self.__class__.device_name)

    def listen(self):

        while True:  # while loop of thread

            client = SimpleUDPClient(self.target_ip, self.target_port)
            command_item = self.q_comand.get(block=True)
            address, value = self._compose(command_item)
            if not address:
                cai = CommandAnswerItem(
                    self.name, command_item.name, (), ComType.failed
                )
                self._put_into_answer_queue(cai)
                continue
            client.send_message(address, value)
            c_address, c_port = client._sock.getsockname()  # get source port
            client._sock.close()

            with ThreadingOSCUDPServer((c_address, c_port), self.dispatcher) as server:
                server.timeout = 0.1
                while self.q_comand.empty():
                    server.handle_request()

    def _compose(self, cmd_item):
        """parse arguments to address and arguments returning OSC message parts.

        First counts the fields in the address string and inserts the arguments into it
        if there are one. Rest of the arguments are returned as new tuple.

        Args:
            cmd_item (CommandItem): CommandItem to be composed from.

        """

        if cmd_item.request:
            address = cmd_item.command_template.request_object
        else:
            address = cmd_item.command_template.command_composition

        try:
            address_arg_count = format_arg_count(address)
            arg_address_tuple = cmd_item.arguments[:address_arg_count]
            arg_argument_tuple = cmd_item.arguments[address_arg_count:]
            if arg_address_tuple:
                address = address.format(*arg_address_tuple)

            self.last_composed = cmd_item

            if len(arg_argument_tuple) == 0:
                return address, ""
            elif len(arg_argument_tuple) == 1:
                return address, arg_argument_tuple[0]
            else:
                return address, list(arg_argument_tuple)
        except TypeError as ex:
            self.logger.warning(
                f"error compoing message {address}:{cmd_item.arguments}. Error "
                f"Message: {ex}"
            )
            return None, None

    def _analyse(self, address, *args):
        """Find corresponding command_template, get answer values and put the in queue.

        First try last send one. Handler for ThreadingOSCUDPServer.

        """

        self.logger.debug(f"analyzing {address} with args {args}")

        cmd_item = None

        try:
            m = re.search(self.last_composed.command_template.answer_analysis, address)
            if not m and ThreadCommunication.dict_command_template:
                for cmd in ThreadCommunication.dict_command_template:
                    m = re.search(cmd.answer_analysis, address)
                    if m:
                        cmd_item = cmd
                        break
        except TypeError as ex:
            self.logger.warning(
                f"error analyzing message {address}:{args}. Error " f"Message: {ex}"
            )
            cai = CommandAnswerItem(
                self.name, None, (address, *args), ComType.unidentifiable
            )
            self._put_into_answer_queue(cai)
            return

        if m:
            values = tuple(m.groups()) + args
        else:
            values = args

        self.logger.debug(f"recived {address} with {values}")

        if not cmd_item:  # match was found in self.last_composed
            command = self.last_composed.command_template.name
            mt = ComType.message_status
        elif m:  # match was found in dict_command_template
            command = cmd_item.name
            if cmd_item.request:
                mt = ComType.request_success
            else:
                mt = ComType.command_success
        else:  # address could not be associated with any command
            command = None
            mt = ComType.unidentifiable

        cai = CommandAnswerItem(self.name, command, values, mt)

        self._put_into_answer_queue(cai)
