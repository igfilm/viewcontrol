"""Test script for CommandObj denon and provided command (cmddenon.yaml)

    Notes
    -----
    Only for Testing. 

    Use provided dictionary to test the communication with the device. Thread
    will print all relevant information

    Sending ACK back to device does not work
    
"""

import threading
import queue
import socket
import time
import re

from commandobj import CommandObj, dict_commandobj, dnc

if __name__ == "__main__":

    TCP_IP = '192.168.178.201'
    TCP_PORT = 9030
    BUFFER_SIZE = 1024

    def listening(q_send, q_recv, q_stat, dict_c=None):
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

        print("started thread")
        
        #creteat socket and connect ...
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TCP_IP, TCP_PORT))

            #timeout for socket.recv, also enssures 20ms between each send
            s.settimeout(.02)

            #while loop of thread
            while True:
                #only send new command from queue conditions are met:
                #  -queue not empty
                if not q_send.empty():
                    val = q_send.get()
                    print("Send: {}".format(val))
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
                                    print("Recv: {:<20} --> {}".format(
                                        data, dict_c.get_full_answer(data)))
                                else:
                                    print("Recv: {:<20}".format(data))
                                q_recv.put(data)
                            #data is a status information
                            elif data.startswith('@0'):
                                #TODO does not work, bd expects ack
                                s.send('ACK'.encode())
                                if(dict_c):
                                    print("Stat: {:<20} --> {}".format(
                                        data, dict_c.get_full_answer(data)))
                                else:
                                    print("Stat: {:<20}".format(data))
                                q_stat.put(data)

    #load dictionary containing commands from yaml file
    dict_denon = dict_commandobj("remotec/cmddenon.yaml")

    #create quee for communication with thread
    q_send = queue.Queue()
    q_recv = queue.Queue()
    q_stat = queue.Queue()

    #create and start thread
    thread = threading.Thread(target=listening, args=(q_send, q_recv, q_stat, dict_denon))
    thread.start()

    #send commands

    #q_send.put(dict_denon.get('Track Number').send_request())
    time.sleep(1)
    q_send.put(dict_denon.get('TMC').send_request())
    #time.sleep(1)
    #q_send.put(dict_denon.get('Track Jump').send_command(1))
    #time.sleep(1)
    #q_send.put(dict_denon.get('Play').send_command())
    #time.sleep(1)
    #q_send.put(dict_denon.get('Pause').send_command())
    time.sleep(1)
    q_send.put(dict_denon.get('Remain Time').send_request())
    time.sleep(1)
    q_send.put(dict_denon.get('Elapse Time').send_request())
    
