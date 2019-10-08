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

from viewcontrol.remotec.commandobj import CommandObj, dict_commandobj, CommandDenon, CommandAtlona

class CommandProcess:

    @staticmethod
    def command_process(command_queue, logger, modules=[]):

        if not logger:
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)

            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.info("Started command_process with pid {}".format(os.getpid()))

        #load dictionary containing commands from yaml file
        dict_atlona = dict_commandobj("viewcontrol/remotec/cmdatlona.yaml")

        if 'CommandAtlona' in modules:  

            #create quee for communication with thread
            q_send_atlona = queue.Queue()
            q_recv_atlona = queue.Queue()
            q_stat_atlona = queue.Queue()

            #create and start thread
            thread_atlona = threading.Thread(
                target=CommandProcess.listening_atlona, 
                name='thread_atlona',
                args=(q_send_atlona, 
                    q_recv_atlona, 
                    q_stat_atlona, 
                    dict_atlona,
                    logger))
            thread_atlona.daemon = True
            thread_atlona.start()

        #load dictionary containing commands from yaml file
        dict_denon = dict_commandobj("viewcontrol/remotec/cmddenon.yaml")

        if 'CommandDenon' in modules:            

            #create quee for communication with thread
            q_send_denon = queue.Queue()
            q_recv_denon = queue.Queue()
            q_stat_denon = queue.Queue()

            #create and start thread
            thread_denon = threading.Thread(
                target=CommandProcess.listening_denon, 
                name='thread_denon',
                args=(q_send_denon, 
                    q_recv_denon, 
                    q_stat_denon, 
                    dict_denon,
                    ),
                kwargs=({'loga': logger,}))
            thread_denon.daemon = True
            thread_denon.start()

        while True:
            cmd_obj = command_queue.get(block=True)
            logger.info("Recived Command: {}".format(cmd_obj))

            if cmd_obj.device == "CommandDenon" and thread_denon.is_alive:
                obj = dict_denon.get(cmd_obj.name_cmd)
                if not obj:
                    logger.warning("Command '{}' not found in dict_deneon!".format(cmd_obj.name_cmd))
                else:    
                    args = cmd_obj.get_args()
                    if args:
                        logger.error("Not Sending: {}".format(obj.send_command(args)))
                        #q_send_denon.put(obj.send_command(args))
                    else:
                        logger.error("Not Sending: {}".format(obj.send_request()))
                        #q_send_denon.put(obj.send_request())                
            
            #q_send_atlona.put(dict_atlona.get('Set Output').send_command(2, 1))
            #q_send_denon.put(dict_denon.get('Track Jump').send_command(1))

    @staticmethod
    def listening_atlona(q_send, q_recv, q_stat, dict_c=None, loga=None):
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

        loga.info("started thread 'listening_atlona'")
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
                        loga.info("Send: {0:<78}R{0}".format(str(val.encode())))
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
                        loga.info("{:<85}{}{:<30}{}".format('-', tmp, str(byt_recv), tmp_n))

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
                                loga.info("Echo: {}".format(str_recv))
                                q_stat.put(str_recv)
                            else:
                                loga.info("Echo: {0:<30} --> {1:<43}E{0}".format(str(byt_recv), str(value)))
                                q_recv.put(str_recv)
                                q_stat.put(str_recv)
                            echo_recived=False
                        else:
                            loga.info("Stat: {0:<30} --> {1:<43}S{0}".format(str(byt_recv), str(value)))
                            q_stat.put(str_recv)

        while True:
            try:
                listen()
            except OSError as ex:  #, ConnectionError, ConnectionRefusedError:
                loga.warning("Atlona Communication Failed ({}). New Try in 1 second.".format(ex.errno))
                time.sleep(1)

    @staticmethod
    def listening_denon(q_send, q_recv, q_stat, dict_c=None, loga=None):
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

        loga.info("started thread 'listening_denon'")

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
                        loga.info("Send: {}".format(val))
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
                                        loga.info("Recv: {:<20} --> {}".format(
                                            data, dict_c.get_full_answer(data)))
                                    else:
                                        loga.info("Recv: {:<20}".format(data))
                                    q_recv.put(data)
                                #data is a status information
                                elif data.startswith('@0'):
                                    #TODO does not work, bd expects ack
                                    s.send('ACK'.encode())
                                    if(dict_c):
                                        loga.info("Stat: {:<20} --> {}".format(
                                            data, dict_c.get_full_answer(data)))
                                    else:
                                        loga.info("Stat: {:<20}".format(data))
                                    q_stat.put(data)

        while True:
            try:
                listen()
            except ConnectionRefusedError as ex:  #, ConnectionError, ConnectionRefusedError:
                loga.warning("Denon Communication Failed ({}). New Try in 10 second.".format(ex.errno))
                time.sleep(10)
            except OSError as ex:  #, ConnectionError, ConnectionRefusedError:
                loga.warning("Denon Communication Failed ({}). New Try in 10 second.".format(ex.errno))
                time.sleep(10)
            

        

#import error will be rised
if __name__ == "__main__":

    def wait_for_enter(pipeA):
        input("Press Enter to Start BluRay")
        pipeA.send("start")

    pipeA, pipeB = multiprocessing.Pipe()

    process = multiprocessing.Process(
        target=CommandProcess.command_process, 
        name="commandprocess",
        args=(pipeB, ))
    process.daemon = True
    process.start()
    
    #x = input("Press Enter to continue...")
    
    #pipeA.send("start")  

    t = threading.Thread(target=wait_for_enter, args=(pipeA,))
    t.start()

    process.join()