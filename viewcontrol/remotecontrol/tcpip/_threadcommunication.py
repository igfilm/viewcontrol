import os
import socket

from viewcontrol.remotecontrol.commanditembase import CommandTemplateList
from viewcontrol.remotecontrol.threadcommunicationbase import ThreadCommunicationBase


class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all tcp/ip communication

    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command string out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both have to be overwritten to adjust the for new devices

    """

    start_seq = NotImplemented
    end_seq = NotImplemented

    def __init__(self, name, target_ip, target_port, buffer_size=1024):
        # target_ip, target_port are a typical config file variable
        self.target_ip = target_ip
        self.target_port = target_port
        self.BUFFER_SIZE = buffer_size
        self.socket = None
        self.last_cmd = None
        super().__init__(name)

    def listen(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.socket:
            self.socket.connect((self.target_ip, self.target_port))

            # timeout for socket.recv, also ensures 20ms between each send
            self.socket.settimeout(0.02)

            while True:

                if not self.q_comand.empty():
                    cmd_obj = self.q_comand.get()
                    val = self.compose(cmd_obj)
                    self.last_cmd = (cmd_obj, val)
                    self.logger.debug("Send: {}".format(val))
                    self.socket.send(val.encode())

                # listen to socket for incoming messages until timeout
                try:
                    str_recv = self.socket.recv(self.BUFFER_SIZE)
                    str_recv = str_recv.decode()
                except socket.timeout:
                    str_recv = None

                if str_recv:
                    self.interpret(str_recv, self.socket)

    def compose(self, cmd_obj):
        if self.dict_command_template:
            dict_obj = self.dict_command_template.get(cmd_obj.name_cmd)
            if not dict_obj:
                self.logger.debug(
                    "Command '{}' not found in dict_deneon! Sending string as it is.".format(
                        cmd_obj.name_cmd
                    )
                )
                str_send = cmd_obj.name_cmd
            else:
                args = cmd_obj.get_parameters()
                if args:
                    str_send = dict_obj.get_send_command(*args)
                else:
                    if dict_obj.string_requ:
                        str_send = dict_obj.get_send_request()
                    else:
                        str_send = dict_obj.get_send_command()
            return str_send
        else:
            self.logger.debug("No dictionary found! Sending string as it is.")
            return str_send

    def interpret(self, val, sock):
        NotImplementedError("please overwrite in subclass")
