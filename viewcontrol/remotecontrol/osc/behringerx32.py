from ._threadcommunication import ThreadCommunication
from ..threadcommunicationbase import DeviceType


class BehringerX32(ThreadCommunication):
    device_name = "Behringer X32"
    device_type = DeviceType.audio


class MidasM32(ThreadCommunication):
    """same osc interface than Behringer X32"""

    device_name = "Midas M32"
    device_type = DeviceType.audio
