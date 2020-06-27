import re

from ._threadcommunication import ThreadCommunication
from ..commanditem import CommandRecvItem
from ..threadcommunicationbase import ComType
from ..threadcommunicationbase import DeviceType


class AtlonaATOMESW32(ThreadCommunication):
    device_name = "Atlona AT-OME-SW32"
    device_type = DeviceType.video

    start_seq = ""
    end_seq = "\r"
    error_seq = r"Command FAILED: \((.*)\)"

    def _analyse(self, str_recv):

        self.logger.debug(f"analyzing {str_recv}")
        # check if received massage is valid
        if str_recv and str_recv.endswith(b"\r\n"):
            # if its equal the send message its the echo seen by client
            # therefore continue and receive the wanted answer
            if (
                not self.feedback_received
                and self.last_send_data
                and self.last_send_data in str_recv
            ):
                self.feedback_received = True
                return

            # decode message
            str_recv = str_recv.decode().rstrip()
            self.logger.debug(f"analyzing string '{str_recv}'")

            try:
                if self.feedback_received:
                    command_template = self.dict_command_template.get(
                        self.last_send_command_item.command
                    )
                    if self._contains_error(str_recv):
                        if self.last_send_command_item.request:
                            mt = ComType.request_failed
                        else:
                            mt = ComType.command_failed
                    else:
                        if self.last_send_command_item.request:
                            mt = ComType.request_success
                        else:
                            mt = ComType.command_success
                    self.feedback_received = False

                    m = re.search(command_template.answer_analysis, str_recv)

                    if m:
                        values = command_template.create_arg_dict(tuple(m.groups()))
                    else:
                        values = ()

                    cai = CommandRecvItem(self.name, command_template.name, values, mt)
                    self._put_into_answer_queue(cai)

            except TypeError as ex:
                self.logger.warning(
                    f"error analyzing message {str_recv}. Error Message: {ex}"
                )
                cai = CommandRecvItem(self.name, None, str_recv, ComType.unidentifiable)
                self._put_into_answer_queue(cai)
                return

    def _telnet_login(self, tn):
        tn.read_until(b"Welcome to TELNET.\r\n")
