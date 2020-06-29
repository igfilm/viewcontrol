import re
import telnetlib
import time

from ..threadcommunicationbase import ThreadCommunicationBase


class ThreadCommunication(ThreadCommunicationBase):
    """Base class for all telnet communication
    
    The 'listen' method is called in the superclass in a while loop with,
    error handling.

    Provides a method for composing the command string out of the command obj
    as well as method to listen for answers or status messages of the device.
    Both are meant to be overwritten to adjust the for new devices

    """

    start_seq = ""
    end_seq = ""
    error_seq = NotImplemented

    def __init__(self, target_ip, target_port, stop_event=None):
        super().__init__(target_ip, target_port, stop_event=stop_event)
        self.last_send_command_item = None
        self.last_send_data = None
        self.feedback_received = False

    def _main(self):

        last_send_time = time.time()

        with telnetlib.Telnet(self.target_ip, port=self.target_port, timeout=5) as tn:
            tn.set_debuglevel(0)
            # and wait until welcome message is received
            self._telnet_login(tn)
            # while loop of thread
            while not self.stop_event.is_set():

                time_tmp = time.time()
                # only send new command from queue conditions are met:
                #  -500ms between commands
                #  -not waiting for echo of a prev command
                #  -queue not empty
                if (
                    time_tmp - last_send_time > 0.5
                    and not self.feedback_received
                    and not self._queue_command.empty()
                ):
                    command_item = self._queue_command.get()
                    self.last_send_command_item = command_item
                    str_send = self._combine_command(self._compose(command_item))
                    self.logger.debug("Send: {0:<78}R{0}".format(str_send))
                    self.last_send_data = str_send.encode()
                    self.feedback_received = False
                    tn.write(self.last_send_data)
                    last_send_time = time_tmp

                # always try to receive messages with given end sequence
                str_recv = tn.read_until(b"\r\n", timeout=0.1)

                if str_recv:
                    self._analyse(str_recv)

    def _analyse(self, str_recv):
        NotImplementedError("please overwrite in subclass")

    def _contains_error(self, string):
        if re.search(self.error_seq, string):
            return True
        else:
            return False

    def _telnet_login(self, tn):
        """connect with device and provide password if needed. Block until connected."""
        NotImplemented("please implement")

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
