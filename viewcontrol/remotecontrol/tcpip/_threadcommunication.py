import socket

from ..threadcommunicationbase import ThreadCommunicationBase


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

    def __init__(self, target_ip, target_port, buffer_size=1024, stop_event=None):
        # target_ip, target_port are a typical config file variable
        self.target_ip = target_ip
        self.target_port = target_port
        self.BUFFER_SIZE = buffer_size
        self.socket = None
        self.last_cmd = None
        super().__init__(self.device_name, stop_event=stop_event)

    def _main(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.socket:
            self.socket.connect((self.target_ip, self.target_port))

            # timeout for socket.recv, also ensures 20ms between each send
            self.socket.settimeout(0.02)

            while not self.stop_event.is_set():

                if not self._queue_command.empty():
                    command_item = self._queue_command.get()
                    str_send = self._combine_command(self._compose(command_item))
                    self.last_cmd = (command_item, str_send)
                    self.logger.debug("Send: {}".format(str_send))
                    self.socket.send(str_send.encode())

                # listen to socket for incoming messages until timeout
                try:
                    str_recv = self.socket.recv(self.BUFFER_SIZE)
                    str_recv = str_recv.decode()
                except socket.timeout:
                    str_recv = None

                if str_recv:
                    self._analyse(str_recv)

    def _combine_command(self, str_command):
        """Adds the start and end sequence to each command string if not already there.
        Args:
            str_command (str): command to be combined
        Returns:
            str: combined command
        """
        tmp_start_seq = ""
        if self.start_seq not in str_command:
            tmp_start_seq = self.start_seq
        tmp_end_seq = ""
        if self.end_seq not in str_command:
            tmp_end_seq = self.end_seq
        return tmp_start_seq + str_command + tmp_end_seq
