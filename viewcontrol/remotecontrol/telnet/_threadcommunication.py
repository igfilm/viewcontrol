import os
import telnetlib
import time

from viewcontrol.remotecontrol.commanditembase import CommandTemplateList
from viewcontrol.remotecontrol.threadcommunicationbase import ThreadCommunicationBase


class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all telnet comunication
    
    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command string out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both are meant to be overwritten to adjust the for new devices

    """

    start_seq = NotImplemented
    end_seq = NotImplemented
    error_seq = NotImplemented

    def __init__(self, name, target_ip, target_port):
        # target_ip, target_port are a typical config file variable
        self.target_ip = target_ip
        self.target_port = target_port
        super().__init__(name)

    def listen(self):

        self.last_send_cmd_obj = None
        self.last_send_data = None
        last_send_time = time.time()
        self.echo_recived = False

        with telnetlib.Telnet(self.target_ip, port=self.target_port, timeout=5) as tn:
            tn.set_debuglevel(0)
            # and wait until welcome message is recived
            tn.read_until(b"Welcome to TELNET.\r\n")
            # while loop of thread
            while True:
                time_tmp = time.time()
                # only send new command from queue conditions are met:
                #  -500ms between commands
                #  -not waiting for echo of a prev command
                #  -queue not empty
                if (
                    time_tmp - last_send_time > 0.5
                    and not self.echo_recived
                    and not self.q_comand.empty()
                ):
                    cmd_obj = self.q_comand.get()
                    self.last_send_cmd_obj = cmd_obj
                    str_send = self.compose(cmd_obj)
                    self.logger.debug("Send: {0:<78}R{0}".format(str_send))
                    self.last_send_data = str_send.encode()
                    tn.write(self.last_send_data)
                    last_send_time = time_tmp

                # allways try to recive messages with given end sequence
                str_recv = tn.read_until(b"\n", timeout=0.1)

                if str_recv:
                    self.interpret(str_recv, tn)

    def compose(self, cmd_obj):
        if self.dict_command_template:
            dict_obj = self.dict_command_template.get(cmd_obj.name_cmd)
            if not dict_obj:
                self.logger.warning(
                    "Command '{}' not found in dict_deneon!".format(cmd_obj.name_cmd)
                )
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

    def interpret(self, val, sock):
        return val
