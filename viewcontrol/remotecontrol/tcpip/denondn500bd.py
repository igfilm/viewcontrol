import re

from ._threadcommunication import ThreadCommunication
from ..threadcommunicationbase import DeviceType, ComType, ComPackage


class DenonDN500BD(ThreadCommunication):
    device_name = "Denon DN-500BD"
    device_type = DeviceType.video

    start_seq = "@0"
    end_seq = "\r"

    def __init__(self, target_ip, target_port):
        self.last_recv = None
        super().__init__("DenonDN500BD", target_ip, target_port)

    def interpret(self, strs_recv, sock):
        # split strings when multiple commands are contained
        m = re.findall(r"((?:ack\+\@|@0\?{0,1}|ack\+|nack|ack)(?:\w|\d)*)", strs_recv)
        if m:
            for str_recv in m:
                # answer is send twice, skip second one
                if str_recv == self.last_recv:
                    continue
                else:
                    self.last_recv = str_recv

                answ_obj = ComPackage(self.name)
                # data is answer of device
                if self.dict_command_template and self.last_cmd:
                    dict_obj = self.dict_command_template.get(self.last_cmd[0].name_cmd)
                else:
                    dict_obj = None
                if str_recv == "nack":
                    answ_obj.command_obj = self.last_cmd[0]
                    answ_obj.send_cmd_string = self.last_cmd[1]
                    if not dict_obj:
                        answ_obj.type = ComType.failed
                    elif not dict_obj.string_requ or self.last_cmd[0].get_parameters():
                        answ_obj.type = ComType.command_failed
                    else:
                        answ_obj.type = ComType.request_failed
                elif str_recv.startswith("ack"):
                    answ_obj.command_obj = self.last_cmd[0]
                    answ_obj.send_cmd_string = self.last_cmd[1]
                    answ_obj.recv_answer_string = str_recv
                    if not dict_obj:
                        answ_obj.type = ComType.success
                    elif not dict_obj.string_requ or self.last_cmd[0].get_parameters():
                        answ_obj.type = ComType.command_success
                    else:
                        answ_obj.type = ComType.request_success
                # data is a status information
                elif str_recv.startswith("@0"):
                    # TODO does not work, bd expects ack
                    # sock.send(chr(0x06).encode())
                    answ_obj.recv_answer_string = str_recv
                    answ_obj.type = ComType.message_status

                if self.dict_command_template and answ_obj.type not in [
                    ComType.failed,
                    ComType.command_failed,
                    ComType.request_failed,
                ]:
                    answ_obj.full_answer = self.dict_command_template.get_full_answer(
                        answ_obj.recv_answer_string
                    )

                self._put_into_answer_queue(answ_obj)
