import re

from ._threadcommunication import ThreadCommunication
from ..threadcommunicationbase import DeviceType, ComType, ComPackage


class AtlonaATOMESW32(ThreadCommunication):
    device_name = "Atlona AT-OME-SW32"
    device_type = DeviceType.video

    start_seq = ""
    end_seq = "\r"
    error_seq = r"Command FAILED: \((.*)\)"

    def __init__(self, target_ip, target_port):
        super().__init__("AtlonaATOMESW32", target_ip, target_port)
        self.echo_recived = False

    def contains_error(self, string):
        if re.search(AtlonaATOMESW32.error_seq, string):
            return True
        else:
            return False

    def interpret(self, str_recv, tn):
        # check if recived massage is valid
        if str_recv and str_recv.endswith(b"\r\n"):
            # if its equal the send message its the echo sen by client
            # therefore continue and recive the wanted answer
            if not self.echo_recived and self.last_send_data in str_recv:
                self.echo_recived = True
                return

            # decode mesage
            str_recv = str_recv.decode().rstrip()

            answ_obj = ComPackage(self.name)
            # if an echo was recived a command was send before,
            # else a status message was send from the client
            if self.echo_recived:
                answ_obj.command_obj = self.last_send_cmd_obj
                answ_obj.recv_answer_string = str_recv
                if self.dict_command_template:
                    dict_obj = self.dict_command_template.get(
                        self.last_send_cmd_obj.name_cmd
                    )
                    if self.contains_error(str_recv):
                        if dict_obj.string_requ:
                            answ_obj.type = ComType.request_failed
                        else:
                            answ_obj.type = ComType.command_failed
                    else:
                        if dict_obj.string_requ:
                            answ_obj.type = ComType.request_success
                        else:
                            answ_obj.type = ComType.command_success
                        # answ_obj.full_answer = self.dict_c.get_full_answer(
                        #    answ_obj.recv_answer_string)
                else:
                    if self.contains_error(str_recv):
                        answ_obj.type = ComType.failed
                    else:
                        answ_obj.type = ComType.success
                self.echo_recived = False
            else:
                answ_obj.recv_answer_string = str_recv
                answ_obj.type = ComType.message_status

            if self.dict_command_template and not answ_obj.type in [
                ComType.failed,
                ComType.command_failed,
                ComType.request_failed,
            ]:
                answ_obj.full_answer = self.dict_command_template.get_full_answer(
                    answ_obj.recv_answer_string
                )

            self._put_into_answer_queue(answ_obj)
