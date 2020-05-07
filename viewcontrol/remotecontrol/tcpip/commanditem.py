from viewcontrol.remotecontrol.commanditembase import CommandItemBase


class DenonDN500BD(CommandItemBase):
    yaml_tag = u"!DenonDN500BD"
    start_seq = "@0"
    end_seq = "\r"
