import socket
import re
import os

from viewcontrol.remotecontrol.threadcommunicationbase \
    import ThreadCommunicationBase, ComPackage, ComType
from viewcontrol.remotecontrol.commanditembase import DictCommandItemLib
import viewcontrol.remotecontrol.tcpip.commanditem as ci

class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all tcp/ip comunication
    
    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command strign out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both are meant to be overwritten to adjust the for new diveces

    """

    def __init__(self, name, target_ip, target_port, dict_c=None, buffer_size=1024):
        #target_ip, target_port are a typical config file variable
        self.target_ip = target_ip
        self.target_port = target_port
        self.BUFFER_SIZE = buffer_size
        if not dict_c:
            dict_c_path = "viewcontrol/remotecontrol/tcpip/dict_{}.yaml".format(name)
            if os.path.exists(dict_c_path):
                dict_c = DictCommandItemLib(dict_c_path)
        self.dict_c = dict_c
        self.socket = None
        self.last_cmd = None
        super().__init__(name)

    def listen(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.socket:
            self.socket.connect((self.target_ip, self.target_port))

            #timeout for socket.recv, also enssures 20ms between each send
            self.socket.settimeout(.02)

            while True:
               #only send new command from queue conditions are met:
                #  -queue not empty
                if not self.q_comand.empty():
                    obj = self.q_comand.get()
                    #TODO do the composition here
                    val = self.compose(obj)
                    self.last_cmd = (obj, val)
                    self.logger.debug("Send: {}".format(val))
                    self.socket.send(val.encode())

                #listent to socket for incomming messages until timeout
                try:
                    str_recv = self.socket.recv(self.BUFFER_SIZE)
                    str_recv = str_recv.decode()
                except socket.timeout:
                    str_recv = None
                
                if str_recv:
                    self.interpret(str_recv, self.socket)


    def compose(self, cmd_obj):
        if self.dict_c:
            dict_obj = self.dict_c.get(cmd_obj.name_cmd)
            if not dict_obj:
                self.logger.debug("Command '{}' not found in dict_deneon! Sending string as it is."
                    .format(cmd_obj.name_cmd))
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
        return val

    def connection_active(self):
        #if self.socket:
        #    self.socket.send
            return True
        #else:
        #    False

class DenonDN500BD(ThreadCommunication):

    def __init__(self, target_ip, target_port):
        self.last_recv = None
        super().__init__("DenonDN500BD", target_ip, target_port)

    def interpret(self, strs_recv, sock):
        #split strings when multiple commands are contained 
        m = re.findall(r'((?:ack\+\@|@0\?{0,1}|ack\+|nack|ack)(?:\w|\d)*)', strs_recv)
        if m:
            for str_recv in m:
                if str_recv == self.last_recv:
                    continue
                else:
                    self.last_recv = str_recv
                
                answ_obj = ComPackage(self.name)
                #data is answer of device
                if self.dict_c and self.last_cmd:
                    dict_obj = self.dict_c.get(self.last_cmd[0].name_cmd)
                else:
                    dict_obj = None
                if str_recv == 'nack':
                    answ_obj.command_obj = self.last_cmd[0]
                    answ_obj.send_cmd_string = self.last_cmd[1]
                    if not dict_obj:
                        answ_obj.type = ComType.failed
                    elif not dict_obj.string_requ or self.last_cmd[0].get_parameters():
                        answ_obj.type = ComType.command_failed
                    else:
                        answ_obj.type = ComType.request_failed
                elif str_recv.startswith('ack'):
                    answ_obj.command_obj = self.last_cmd[0]
                    answ_obj.send_cmd_string = self.last_cmd[1]
                    answ_obj.recv_answer_string = str_recv
                    if not dict_obj:
                        answ_obj.type = ComType.success
                    elif not dict_obj.string_requ or self.last_cmd[0].get_parameters():
                        answ_obj.type = ComType.command_success
                    else:
                        answ_obj.type = ComType.request_success
                #data is a status information
                elif str_recv.startswith('@0'):
                    #TODO does not work, bd expects ack
                    #sock.send(chr(0x06).encode())
                    answ_obj.recv_answer_string = str_recv
                    answ_obj.type = ComType.message_status                               
                    
                if self.dict_c and not answ_obj.type in [ComType.failed, ComType.command_failed, ComType.request_failed]:
                    answ_obj.full_answer = self.dict_c.get_full_answer(
                        answ_obj.recv_answer_string)

                self.put_queue(answ_obj)
