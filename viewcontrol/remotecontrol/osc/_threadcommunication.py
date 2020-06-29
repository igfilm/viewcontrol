import re
import socket

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from ..commanditem import CommandRecvItem
from ..commanditem import CommandSendItem
from ..commanditem import format_arg_count
from ..threadcommunicationbase import ComType
from ..threadcommunicationbase import ThreadCommunicationBase


class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all OSC communication

    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command string out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both are meant to be overwritten to adjust the for new devices

    """

    def __init__(self, target_ip, target_port, stop_event=None):
        super().__init__(target_ip, target_port, stop_event=stop_event)
        self._dispatcher = Dispatcher()
        self._dispatcher.set_default_handler(self._analyse)
        self.last_composed = None

    # noinspection PyProtectedMember,PyProtectedMember
    def _main(self):

        client = _SimpleUDPClient(self.target_ip, self.target_port)

        server = _ThreadingOSCUDPServer(client.sock_connection, self._dispatcher)
        server.timeout = 0.01

        self.logger.debug(f"osc client connection: {client.sock_connection}")
        self.logger.debug(f"osc server connection: {server.sock_connection}")

        while not self.stop_event.is_set():  # while loop of thread

            while self._queue_command.empty():
                server.handle_request()
                if self.stop_event.is_set():
                    return

            command_item = self._queue_command.get()
            if not command_item:
                # used if subclass does decides at compose time not to send the command
                continue
            address, value = self._compose(command_item)
            if not address:
                continue
            if address is TypeError:
                # address and value are none when error occurred during composing
                cai = CommandRecvItem(
                    self.device_name, command_item.command, (), ComType.failed
                )
                self._put_into_answer_queue(cai)
                continue
            client.send_message(address, value)

    def _compose(self, command_item):
        """parse arguments to address and arguments returning OSC message parts.

        First counts the fields in the address string and inserts the arguments into it
        if there are one. Rest of the arguments are returned as new tuple.

        Args:
            command_item (CommandSendItem): CommandItem to be composed from.

        """

        command_template = self.dict_command_template[command_item.command]
        if command_item.request:
            address = command_template.request_composition
        else:
            address = command_template.command_composition

        if isinstance(command_item.arguments, dict):
            arguments = command_template.sorted_tuple_from_dict(command_item.arguments)
        else:
            arguments = command_item.arguments

        try:
            address_arg_count = format_arg_count(address)
            arg_address_tuple = arguments[:address_arg_count]
            arg_argument_tuple = arguments[address_arg_count:]
            if arg_address_tuple:
                address = address.format(*arg_address_tuple)

            self.last_composed = command_item

            if len(arg_argument_tuple) == 0:
                return address, ""
            if len(arg_argument_tuple) == 1:
                return address, arg_argument_tuple[0]
            return address, list(arg_argument_tuple)

        except TypeError as ex:
            self.logger.warning(
                f"error composing message {address}:{command_item.arguments}. Error "
                f"Message: {ex}"
            )
            return TypeError, TypeError

    def _analyse(self, address, *args):

        self.logger.debug(f"analyzing {address} with args {args}")

        m = None
        cmd_template = None
        in_last_composed = False

        try:
            command_template_last = self.dict_command_template[
                self.last_composed.command
            ]
            if command_template_last.answer_analysis:
                m = re.search(command_template_last.answer_analysis, address)
                cmd_template = command_template_last
                in_last_composed = True

            if not m:
                for name, command_template in self.dict_command_template.items():
                    if not command_template.answer_analysis:
                        continue
                    m = re.search(command_template.answer_analysis, address)
                    if m:
                        cmd_template = command_template
                        break

            values = None
            if cmd_template:
                if m:
                    values = cmd_template.create_arg_dict(tuple(m.groups()) + args)
                else:
                    values = cmd_template.create_arg_dict(args)

            if in_last_composed:  # match was found in self.last_composed
                command = self.last_composed.command
                if self.last_composed.request:
                    mt = ComType.request_success
                else:
                    mt = ComType.command_success
            elif m:  # match was found in dict_command_template
                command = cmd_template.name
                mt = ComType.message_status
            else:  # address could not be associated with any command
                command = None
                values = (address, args)
                mt = ComType.unidentifiable

            cai = CommandRecvItem(self.name, command, values, mt)

            self._put_into_answer_queue(cai)

        except TypeError as ex:
            self.logger.warning(
                f"error analyzing message {address}:{args}. Error Message: {ex}"
            )
            cai = CommandRecvItem(
                self.name, None, (address, *args), ComType.unidentifiable
            )
            self._put_into_answer_queue(cai)
            return


class _SimpleUDPClient(SimpleUDPClient):
    def __init__(self, target_ip, target_port):
        super(_SimpleUDPClient, self).__init__(target_ip, target_port)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("", 0))

    @property
    def sock_connection(self):
        return self._sock.getsockname()


class _ThreadingOSCUDPServer(ThreadingOSCUDPServer):

    allow_reuse_address = True

    @property
    def sock_connection(self):
        return self.socket.getsockname()
