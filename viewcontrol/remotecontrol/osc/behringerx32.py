from ._threadcommunication import ThreadCommunication
from ..commanditem import CommandSendItem
from ..threadcommunicationbase import DeviceType
from ...util.timing import RepeatedTimer


class BehringerX32(ThreadCommunication):
    device_name = "Behringer X32"
    device_type = DeviceType.audio

    def __init__(self, target_ip, target_port, stop_event=None):
        super().__init__(target_ip, target_port, stop_event=stop_event)
        self._timer_xremote = RepeatedTimer(9.9, self._send_xremote_request)

    def _send_xremote_request(self):
        command_send_item = CommandSendItem(self.device_name, "XRemote", request=True)
        self._put_into_command_queue(command_send_item, comment="repeating XRemote")

    def _compose(self, command_item):
        if command_item.command == "XRemote repeating":
            if command_item.arguments[0] == "ON":
                self._timer_xremote.start()
                self._send_xremote_request()
            else:
                self._timer_xremote.cancel()
            self.logger.info(f"data {command_item} not send. data is control data")
            return None, None
        else:
            self.logger.warning(command_item)
            return super()._compose(command_item)

    def _on_exit(self):
        self._timer_xremote.cancel()
        super()._on_exit()


class MidasM32(BehringerX32):
    """same osc interface than Behringer X32"""

    device_name = "Midas M32"
    device_type = DeviceType.audio
