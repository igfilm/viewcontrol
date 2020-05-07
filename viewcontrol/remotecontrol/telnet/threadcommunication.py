import telnetlib
import os
import re
import time

from viewcontrol.remotecontrol.threadcommunicationbase import (
    ThreadCommunicationBase,
    ComPackage,
    ComType,
)
from viewcontrol.remotecontrol.commanditembase import DictCommandItemLib
import viewcontrol.remotecontrol.telnet.commanditem as ci


class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all telnet comunication
    
    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command strign out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both are meant to be overwritten to adjust the for new diveces

    """

    def __init__(self, name, target_ip, target_port, dict_c=None):
        # target_ip, target_port are a typical config file variable
        self.target_ip = target_ip
        self.target_port = target_port
        if not dict_c:
            dict_c_path = "viewcontrol/remotecontrol/telnet/dict_{}.yaml".format(name)
            if os.path.exists(dict_c_path):
                dict_c = DictCommandItemLib(dict_c_path)
        self.dict_c = dict_c
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
        if self.dict_c:
            dict_obj = self.dict_c.get(cmd_obj.name_cmd)
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

    def connection_active(self):
        return True


class AtlonaATOMESW32(ThreadCommunication):
    def __init__(self, target_ip, target_port):
        super().__init__("AtlonaATOMESW32", target_ip, target_port)
        self.echo_recived = False

    def contains_error(self, string):
        if re.search(ci.AtlonaATOMESW32.error_seq, string):
            return True
        else:
            return False

    def interpret(self, str_recv, tn):
        # check if recived massage is valid
        if str_recv and str_recv.endswith(b"\r\n"):
            # if its equal the send message its the echo sen by client
            # therefore continue and recive the wanted answer
            if not self.echo_recived and self.last_send_data in str_recv:
                self.echo_recived = True
                return

            # decode mesage
            str_recv = str_recv.decode().rstrip()

            answ_obj = ComPackage(self.name)
            # if an echo was recived a command was send before,
            # else a status message was send from the client
            if self.echo_recived:
                answ_obj.command_obj = self.last_send_cmd_obj
                answ_obj.recv_answer_string = str_recv
                if self.dict_c:
                    dict_obj = self.dict_c.get(self.last_send_cmd_obj.name_cmd)
                    if self.contains_error(str_recv):
                        if dict_obj.string_requ:
                            answ_obj.type = ComType.request_failed
                        else:
                            answ_obj.type = ComType.command_failed
                    else:
                        if dict_obj.string_requ:
                            answ_obj.type = ComType.request_success
                        else:
                            answ_obj.type = ComType.command_success
                        # answ_obj.full_answer = self.dict_c.get_full_answer(
                        #    answ_obj.recv_answer_string)
                else:
                    if self.contains_error(str_recv):
                        answ_obj.type = ComType.failed
                    else:
                        answ_obj.type = ComType.success
                self.echo_recived = False
            else:
                answ_obj.recv_answer_string = str_recv
                answ_obj.type = ComType.message_status

            if self.dict_c and not answ_obj.type in [
                ComType.failed,
                ComType.command_failed,
                ComType.request_failed,
            ]:
                answ_obj.full_answer = self.dict_c.get_full_answer(
                    answ_obj.recv_answer_string
                )

            self.put_queue(answ_obj)
