import multiprocessing
import threading
import queue
import socket
import telnetlib
import time
import re

import logging
import sys
import os

from blinker import signal

from viewcontrol.remotec.commandobj import CommandObj, dict_commandobj, CommandDenon, CommandAtlona

import viewcontrol.show


class ProcessCmd(multiprocessing.Process):
    
    def __init__(self, logger_config, queue_status, queue_comand, modules, **kwargs):
        super().__init__(name='ProcessCmd', **kwargs)
        self._dummy = CommandProcess(logger_config, queue_status, queue_comand, modules, self.name)

    def run(self):
        self._dummy.run()

class ThreadCmd(threading.Thread):

    def __init__(self, logger, queue_status, queue_comand, modules, **kwargs):
        super().__init__(name='ThreadCmd', **kwargs)
        self._dummy = CommandProcess(logger, queue_status, queue_comand, modules, self.name)

    def run(self):
        self._dummy.run()


class CommandProcess:
    """
    WARNING: all commands are send without any delay
    add listeners to send command events via status queue to main process
    """

    def __init__(self, logger_config, queue_status, queue_comand, modules, parent_name):
        self.logger_config = logger_config
        self.queue_status = queue_status
        self.queue_comand = queue_comand
        self.modules = modules
        self.name = parent_name

        self.can_run = threading.Event()
        self.can_run.set()

        self.send_status = signal("send_status")
        self.send_status.connect(self.subsr_send_status)

    def run(self):

        if isinstance(self.logger_config, logging.Logger):
            self.logger = self.logger_config
        else:
            logging.config.dictConfig(self.logger_config)
            self.logger = logging.getLogger()
        self.logger.info("Started command_process with pid {}".format(os.getpid()))

        try:
            #load dictionary containing commands from yaml file
            dict_atlona = dict_commandobj("viewcontrol/remotec/cmdatlona.yaml")

            if 'CommandAtlona' in self.modules:  

                #create quee for communication with thread
                q_send_atlona = queue.Queue()
                q_recv_atlona = queue.Queue()
                q_stat_atlona = queue.Queue()

                #create and start thread
                thread_atlona = threading.Thread(
                    target=self.listening_atlona, 
                    name='thread_atlona',
                    args=(q_send_atlona, 
                        q_recv_atlona,
                        q_stat_atlona,                        
                        dict_atlona,
                        ),
                    daemon=True
                    )
                thread_atlona.start()

            #load dictionary containing commands from yaml file
            dict_denon = dict_commandobj("viewcontrol/remotec/cmddenon.yaml")

            if 'CommandDenon' in self.modules:            

                #create quee for communication with thread
                q_send_denon = queue.Queue()
                q_recv_denon = queue.Queue()
                q_stat_denon = queue.Queue()

                #create and start thread
                thread_denon = threading.Thread(
                    target=self.listening_denon, 
                    name='thread_denon',
                    args=(q_send_denon,
                        q_recv_denon,
                        q_stat_denon,
                        dict_denon,
                        ),
                    daemon=True)
                thread_denon.daemon = True
                thread_denon.start()

            while True:
                cmd_obj = self.queue_comand.get(block=True)
                self.logger.info("~~> recived data: '{}':'{}'"
                    .format(type(cmd_obj), str(cmd_obj)))
                if isinstance(cmd_obj, viewcontrol.show.Command):
                    pass
                elif isinstance(cmd_obj, str):
                    # implemnt pausing and handling of delayed commands
                    if cmd_obj == "pause":
                        pass
                    elif cmd_obj == "resume":
                        pass
                    elif cmd_obj == "next":
                        pass
                    continue
                else:
                    continue

                self.logger.info("Recived Command: {}".format(cmd_obj))

                if cmd_obj.device == "CommandDenon" and thread_denon and thread_denon.is_alive:
                    obj = dict_denon.get(cmd_obj.name_cmd)
                    if not obj:
                        self.logger.warning("Command '{}' not found in dict_deneon!"
                            .format(cmd_obj.name_cmd))
                        continue
                elif cmd_obj.device == "CommandAtlona" and thread_atlona and thread_atlona.is_alive:
                    obj = dict_atlona.get(cmd_obj.name_cmd)
                    if not obj:
                        self.logger.warning("Command '{}' not found in dict_atlona!"
                            .format(cmd_obj.name_cmd))
                        continue

                args = cmd_obj.get_args()
                if args:
                    str_send = obj.send_command(*args)
                else:
                    if obj.string_requ:
                        str_send = obj.send_request()
                    else:
                        str_send = obj.send_command()            
                
                if cmd_obj.device == "CommandDenon":
                    q_send_denon.put(str_send)
                    #threading.Timer(cmd_obj.delay, send_denon, args=str_send)
                elif cmd_obj.device == "CommandAtlona":
                    q_send_atlona.put(str_send)
                    #threading.Timer(cmd_obj.delay, q_send_atlona.put, args=str_send)   
                self.logger.info("Added command string '{}' to device '{}' queue."
                    .format(str_send, cmd_obj.device))

        except Exception as e:
            try:
                raise
            finally:
                self.logger.error("Uncaught exception in process '{}'"
                        .format(self.name), 
                    exc_info=(e))
    
    def subsr_send_status(self, status):
        self.queue_status.put(status)
        self.logger.debug("<~~ send data: '{}':'{}'"
            .format(type(status), str(status)))

    def listening_atlona(self, q_send, q_recv, q_stat, dict_c=None):
        """Thread function for listening and writing via telnet protocoll

        Sends commands in q_send with an delay of 500ms delay between each
        command and continuesly listens for incomming messages. Prints all
        send and recived messages to stdout
            
        Args:
            q_send (queue.Queue): Queue for commands to be send.
            q_recv (queue.Queue): Queue for returning answers of commands q_send
            q_stat (queue.Queue): Queue for returning stat messages recived
            dict_c (dict, optional): dictionary of commands for device

        """

        self.logger.info("started thread 'listening_atlona'")
        IP_ADDR = '192.168.178.202'

        def listen():

            last_send_data = b''        
            last_send_time = time.time()
            echo_recived = False
            
            #counter for testing, will be 0 or one when no stat change or error 
            tmp_n = 1

            #connect to switch via tellnet ...
            with telnetlib.Telnet(IP_ADDR, port=23, timeout=5) as tn:
                tn.set_debuglevel(0)
                #and wait until welcome message is recived
                tn.read_until(b'Welcome to TELNET.\r\n')
                #while loop of thread
                while True:
                    time_tmp = time.time()
                    #only send new command from queue conditions are met:
                    #  -500ms between commands
                    #  -not waiting for echo of a prev command
                    #  -queue not empty
                    if time_tmp-last_send_time > .5 \
                            and not echo_recived \
                            and not q_send.empty():
                        val = q_send.get()
                        self.logger.info("Send: {0:<78}R{0}".format(str(val.encode())))
                        last_send_data = val.encode()
                        tn.write(last_send_data)
                        last_send_time = time_tmp

                    #allways try to recive messages with given end sequence
                    byt_recv = tn.read_until(b'\n', timeout=.1)

                    #just for debuging: print plain recived data
                    if(byt_recv):
                        if echo_recived: 
                            tmp = 'T'
                            tmp_n = tmp_n+1
                        else: 
                            tmp = 'F'
                            tmp_n=tmp_n-1
                        self.logger.info("{:<85}{}{:<30}{}".format('-', tmp, str(byt_recv), tmp_n))

                    #check if recived massage is valid         
                    if(byt_recv and byt_recv.endswith(b'\r\n')):
                        #if its equal the send message its the echo sen by client
                        #therefore continue and recive the wanted answer                    
                        if not echo_recived and last_send_data in byt_recv:
                            echo_recived = True
                            continue

                        #decode mesage and find the corresponding entyr in the
                        #dictionary (when provided)
                        str_recv = byt_recv.decode().rstrip()
                        if(dict_c):
                            value = dict_c.get_full_answer(str_recv)
                        else:
                            value = (None, str_recv)

                        #if an echo was recived a command was send bevore,
                        #else a status message was sen from the client
                        if echo_recived:
                            #if command failed
                            if re.search(CommandAtlona.error_seq, str_recv):
                                self.logger.info("Echo: {}".format(str_recv))
                                q_stat.put(str_recv)
                                self.send_status.send(("stat", value))
                            else:
                                self.logger.info("Echo: {0:<30} --> {1:<43}E{0}".format(str(byt_recv), str(value)))
                                q_recv.put(str_recv)
                                self.send_status.send(("recv", value))
                                #q_stat.put(str_recv)
                            echo_recived=False
                        else:
                            self.logger.info("Stat: {0:<30} --> {1:<43}S{0}".format(str(byt_recv), str(value)))
                            q_stat.put(str_recv)
                            self.send_status.send(("stat", value))

        while True:
            try:
                listen()
            except OSError as ex:  #, ConnectionError, ConnectionRefusedError:
                self.logger.warning("Atlona Communication Failed ({}). New Try in 10 second.".format(ex.errno))
                time.sleep(10)


    def listening_denon(self, q_send, q_recv, q_stat, dict_c=None):
        """Thread function for listening and writing via telnet protocoll

        Sends commands in q_send with an delay of 500ms delay between each
        command and continuesly listens for incomming messages. Prints all
        send and recived messages to stdout
            
        Args:
            q_send (queue.Queue): Queue for commands to be send.
            q_recv (queue.Queue): Queue for returning answers of commands q_send
            q_stat (queue.Queue): Queue for returning stat messages recived
            dict_c (dict, optional): dictionary of commands for device

        """

        self.logger.info("started thread 'listening_denon'")

        TCP_IP = '192.168.178.201'
        TCP_PORT = 9030
        BUFFER_SIZE = 1024

        def listen():

            #creteat socket and connect ...
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((TCP_IP, TCP_PORT))

                #timeout for socket.recv, also enssures 20ms between each send
                s.settimeout(.02)

                while True:
                    #only send new command from queue conditions are met:
                    #  -queue not empty
                    if not q_send.empty():
                        val = q_send.get()
                        self.logger.info("Send: {}".format(val))
                        s.send(val.encode())

                    #listent to socket for incomming messages until timeout
                    try:
                        str_recv = s.recv(BUFFER_SIZE).decode()
                    except socket.timeout:
                        str_recv = None

                    #when a string was recived extract message and type
                    if str_recv:
                        #split strings when multiple commands are contained 
                        m = re.findall(r'((?:ack\+\@|@0\?{0,1}|ack\+)(?:\w|\d)*)', 
                            str_recv)
                        if m:
                            for data in m:
                                #data is answer of device
                                if data.startswith('ack+'):
                                    if(dict_c):
                                        self.logger.info("Recv: {:<20} --> {}".format(
                                            data, dict_c.get_full_answer(data)))
                                    else:
                                        self.logger.info("Recv: {:<20}".format(data))
                                    q_recv.put(data)
                                #data is a status information
                                elif data.startswith('@0'):
                                    #TODO does not work, bd expects ack
                                    s.send('ACK'.encode())
                                    if(dict_c):
                                        self.logger.info("Stat: {:<20} --> {}".format(
                                            data, dict_c.get_full_answer(data)))
                                    else:
                                        self.logger.info("Stat: {:<20}".format(data))
                                    q_stat.put(data)

                        #temporary until proper Testing with device can be done
                        if m:
                            for str_data in m:
                                if(dict_c):
                                    value = dict_c.get_full_answer(str_data)
                                else:
                                    value = (None, str_data)
                            self.send_status.send(('stat', value))

        while True:
            try:
                listen()
            except ConnectionRefusedError as ex:  #, ConnectionError, ConnectionRefusedError:
                self.logger.warning("Denon Communication Failed ({}). New Try in 10 second.".format(ex.errno))
                time.sleep(10)
            except OSError as ex:  #, ConnectionError, ConnectionRefusedError:
                self.logger.warning("Denon Communication Failed ({}). New Try in 10 second.".format(ex.errno))
                time.sleep(10)