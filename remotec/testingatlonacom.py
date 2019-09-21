"""Test script for CommandObj atlona and provided command (cmdatlona.yaml)

    Notes
    -----
    Only for Testing. 

    Use provided dictionary to test the communication with the device. Thread
    will print all relevant information

    The Atlona device seems to send status messages in
    between of answers. E.g: in the the recived message is 
    'fuuHello Worldbar' where 'fuubar' should be recived and 'Hello World' is
    a status message (cariage return and new line ommited)
    
"""

import threading
import queue
import telnetlib
import time
import re

from commandobj import CommandObj, dict_commandobj, atlona

if __name__ == "__main__":

    IP_ADDR = '192.168.178.202'

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
                    print("Send: {0:<78}R{0}".format(str(val.encode())))
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
                    print("{:<85}{}{:<30}{}".format('-', tmp, str(byt_recv), tmp_n))

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
                        if re.search(atlona.error_seq, str_recv):
                            print("Echo: {}".format(str_recv))
                            q_stat.put(str_recv)
                        else:
                            print("Echo: {0:<30} --> {1:<43}E{0}".format(str(byt_recv), str(value)))
                            q_recv.put(str_recv)
                            q_stat.put(str_recv)
                        echo_recived=False
                    else:
                        print("Stat: {0:<30} --> {1:<43}S{0}".format(str(byt_recv), str(value)))
                        q_stat.put(str_recv)
                    

    #load dictionary containing commands from yaml file
    dict_atlona = dict_commandobj("remotec/cmdatlona.yaml")

    #create quee for communication with thread
    q_send = queue.Queue()
    q_recv = queue.Queue()
    q_stat = queue.Queue()

    #create and start thread
    thread = threading.Thread(target=listening, args=(q_send, q_recv, q_stat, dict_atlona))
    thread.start()

    #send commands i times
    i = 20
    while i > 0:
        q_send.put(dict_atlona.get('Status').send_request())
        q_send.put('Type\r')
        q_send.put(dict_atlona.get('PWSTA').send_request())
        q_send.put(dict_atlona.get('PWON').send_command())
        q_send.put(dict_atlona.get('Blink').send_command('on'))
        q_send.put(dict_atlona.get('Lock').send_command())
        q_send.put(dict_atlona.get('InputStatus').send_request())
        q_send.put(dict_atlona.get('Set Output').send_command(i%3+1, 1))
        q_send.put(dict_atlona.get('Set Output').send_command(i%3+1, 2))
        q_send.put(dict_atlona.get('InputStatus').send_request())
        q_send.put(dict_atlona.get('Unlock').send_command())
        q_send.put(dict_atlona.get('Blink').send_command('off'))
        #q_send.put(dict_atlona.get('PWOFF').send_command())
        i = i-1
    q_send.put(dict_atlona.get('System sta').send_command())
    q_send.put('IPCFG\r')
    