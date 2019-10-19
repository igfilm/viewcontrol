import socket
import re
import os

from viewcontrol.remotecontrol.threadcommunicationbase import ThreadCommunicationBase
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
        super().__init__(name)

    def listen(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.target_ip, self.target_port))

            #timeout for socket.recv, also enssures 20ms between each send
            s.settimeout(.02)

            while True:
               #only send new command from queue conditions are met:
                #  -queue not empty
                if not self.q_send.empty():
                    val = self.q_send.get()
                    #TODO do the composition here
                    val = self.compose(val)
                    self.logger.info("Send: {}".format(val))
                    s.send(val.encode())

                #listent to socket for incomming messages until timeout
                try:
                    str_recv = s.recv(self.BUFFER_SIZE).decode()
                except socket.timeout:
                    str_recv = None

                if str_recv:
                    self.interpret(str_recv, s)


    def compose(self, cmd_obj):
        if self.dict_c:
            dict_obj = self.dict_c.get(cmd_obj.name_cmd)
            if not dict_obj:
                self.logger.warning("Command '{}' not found in dict_deneon!"
                    .format(cmd_obj.name_cmd))
            else:
                args = cmd_obj.get_args()
                if args:
                    str_send = dict_obj.send_command(*args)
                else:
                    if dict_obj.string_requ:
                        str_send = dict_obj.send_request()
                    else:
                        str_send = dict_obj.send_command() 
            return str_send   

    def interpret(self, val, sock):
        return val


class DenonDN500BD(ThreadCommunication):

    def __init__(self, target_ip, target_port):
        super().__init__("DenonDN500BD", target_ip, target_port)

    def interpret(self, str_recv, sock):
        #split strings when multiple commands are contained 
        m = re.findall(r'((?:ack\+\@|@0\?{0,1}|ack\+)(?:\w|\d)*)', str_recv)
        if m:
            for data in m:
                #data is answer of device
                if data.startswith('ack+'):
                    if(self.dict_c):
                        self.logger.info("Recv: {:<20} --> {}".format(
                            data, self.dict_c.get_full_answer(data)))
                    else:
                        self.logger.info("Recv: {:<20}".format(data))
                    self.put_q_recv((self.name, data))
                #data is a status information
                elif data.startswith('@0'):
                    #TODO does not work, bd expects ack
                    sock.send('ACK'.encode())
                    if(self.dict_c):
                        self.logger.info("Stat: {:<20} --> {}".format(
                            data, self.dict_c.get_full_answer(data)))
                    else:
                        self.logger.info("Stat: {:<20}".format(data))
                    self.put_q_stat((self.name, data))
