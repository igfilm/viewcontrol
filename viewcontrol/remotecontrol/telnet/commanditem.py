from viewcontrol.remotecontrol.commanditembase import CommandItemBase


class AtlonaATOMESW32(CommandItemBase):
    yaml_tag = u"!AtlonaATOMESW32"
    start_seq = ""
    end_seq = "\r"
    error_seq = r"Command FAILED: \((.*)\)"
