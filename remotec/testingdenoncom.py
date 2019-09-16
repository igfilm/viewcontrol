import threading
import queue
import socket
import time

from commandobj import CommandObj, dict_commandobj

if __name__ == "__main__":

    def listening(q_send, q_recv, q_stat, dict_c=None):
        print("started thread")
        TCP_IP = '192.168.178.201'
        TCP_PORT = 9030
        BUFFER_SIZE = 1024
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((TCP_IP, TCP_PORT))
            s.settimeout(.02)
            while True:
                if not q_send.empty():
                    val = q_send.get()
                    print("Send: {}".format(val))
                    s.send(val.encode())
                try:
                    data = s.recv(BUFFER_SIZE).decode()
                except socket.timeout:
                    data = None
                if data:
                    if data.startswith('ack+'):
                        if(dict_c):
                            print("Recv: {:<20} --> {}".format(
                                data, dict_c.get_full_answer(data)))
                        else:
                            print("Recv: {:<20}".format(data))
                        q_recv.put(data)
                    elif data.startswith('@0'):
                        #TODO does not work, bd expects ack
                        s.send('ACK'.encode())
                        if(dict_c):
                            print("Stat: {:<20} --> {}".format(
                                data, dict_c.get_full_answer(data)))
                        else:
                            print("Stat: {:<20}".format(data))
                        q_stat.put(data)


    dict_denon = dict_commandobj("remotec/testing.yaml")

    q_send = queue.Queue()
    q_recv = queue.Queue()
    q_stat = queue.Queue()

    thread = threading.Thread(target=listening, args=(q_send, q_recv, q_stat, dict_denon))
    thread.start()

    
    dict_denon.get_command_from_answer('@0STPP')

    fuu = dict_denon.get_full_answer('@0STPP')

    q_send.put(dict_denon.get('Track Number').send_request())
    time.sleep(1)
    q_send.put(dict_denon.get('TMC').send_request())
    time.sleep(1)
    q_send.put(dict_denon.get('Track Jump').send_command(1))
    time.sleep(1)
    q_send.put(dict_denon.get('Play').send_command())
    time.sleep(1)
    q_send.put(dict_denon.get('Pause').send_command())
    
