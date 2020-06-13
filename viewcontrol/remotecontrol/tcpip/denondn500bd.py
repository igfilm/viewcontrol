import re

from ._threadcommunication import ThreadCommunication
from ..commanditem import CommandRecvItem
from ..threadcommunicationbase import DeviceType
from ..threadcommunicationbase import ComType


class DenonDN500BD(ThreadCommunication):
    device_name = "Denon DN-500BD"
    device_type = DeviceType.video

    start_seq = "@0"
    end_seq = "\r"
    error_seq = "@0BDERBUSY"

    def __init__(self, target_ip, target_port):
        self.last_recv = None
        super().__init__(target_ip, target_port)

    def _analyse(self, str_recv):

        self.logger.debug(f"analyzing {str_recv}")
        # split strings when multiple commands are contained
        m = re.findall(r"((?:ack\+@|@0\??|ack\+|nack|ack)(?:\w|\d)*)", str_recv)
        if m:
            for str_recv in m:
                try:
                    # answer is send twice, skip second one
                    if str_recv == self.last_recv:
                        continue
                    else:
                        self.last_recv = str_recv

                    m2 = None
                    command_template = None

                    if "ack" in str_recv:
                        command_item, _ = self.last_cmd
                        if str_recv == "nack":
                            if command_item.request:
                                mt = ComType.request_failed
                            else:
                                mt = ComType.command_failed
                        else:
                            if command_item.request:
                                mt = ComType.request_success
                            else:
                                mt = ComType.command_success
                        command_template = self.dict_command_template[
                            command_item.command
                        ]

                    # data is a status information, command must be looked up.
                    elif str_recv.startswith("@0"):
                        mt = ComType.message_status

                        for command_template in self.dict_command_template.values():
                            if not command_template.answer_analysis:
                                continue
                            m2 = re.search(command_template.answer_analysis, str_recv)
                            if m2:
                                break
                    else:
                        raise ValueError("string can not be classified")

                    # starts with ack or @0
                    if command_template:
                        if not m2:
                            m2 = re.search(command_template.answer_analysis, str_recv)

                        if m2:
                            values = command_template.create_arg_dict(
                                tuple(m2.groups())
                            )
                        else:
                            values = ()
                    else:
                        values = None

                    cai = CommandRecvItem(self.name, command_template.name, values, mt)
                    self._put_into_answer_queue(cai)

                except (TypeError, ValueError) as ex:
                    self.logger.warning(
                        f"error analyzing message {str_recv}. Error Message: {ex}"
                    )
                    cai = CommandRecvItem(
                        self.name, None, str_recv, ComType.unidentifiable
                    )
                    self._put_into_answer_queue(cai)
