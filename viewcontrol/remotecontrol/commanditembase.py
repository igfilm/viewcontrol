import logging
import pathlib
import string

import yaml


class CommandItem:

    def __init__(self, device, command):
        self.device = device
        self.command = command


class CommandSendItem(CommandItem):
    """Object holding content of messages to be send and additional information.

    Args:
        device (str): name representation of device.
        command (str): name representation of command.
        arguments (dict or tuple): arguments to be send of any type that is supported by
            device. If a dict is used order does not matter. A tuple will be parsed into
            the arguments in the order they are.
        request (bool): true if request object has to be used otherwise
            command_composition string will be used. Defaults to False.

    For Attributes see Arguments. Attributes are identical with arguments.
    """

    def __init__(self, device, command, arguments=(), request=True):
        super().__init__(device, command)
        self.arguments = arguments
        self.request = request


class CommandRecvItem:
    """Object holding content of received messages and additional information.

    Args:
        device (str): name representation of device.
        command (str): name representation of command.
        values (dict or tuple): tuple if command is None.
        message_type (ComType): condition under which message was received.

    For Attributes see Arguments. Attributes are identical with arguments.
    """

    def __init__(self, device, command, values, message_type):
        self.device = device
        self.command = command
        self.values = values
        self.message_type = message_type

    def __str__(self):
        return f"{self.device}({self.command})-{self.values}-{self.message_type}"


class CommandTemplate(yaml.YAMLObject):
    """Stores one single command and provides functions for message handling.

    Arguments are identical to Attributes. See Attributes.

    Attributes:
        name (str): short and easy name of the command (for drop-down list).
        description (str): description of command including parameter description.
        request_object (obj): object to be send to request something, usually a string.
        command_composition (obj): object composing the object to be send from
            arguments. Simplest implementation is a string following PEP 3101 of
            str.format() for the arguments parsing.
        answer_analysis (obj): object holding information how to extract data from
            received message. Simplest implementation is be a regex string with
            capture groups. Trivial implementation is just passing the value.
        argument_mappings (list of dict): assignment of human readable responses to
            command objects/strings or discrete ranges. Must be a list where the dict
            position in list corresponds to argument position. For continues ranges use
            the dict keys as keyword e.g {min: 0, max:255}.

    """

    yaml_loader = yaml.SafeLoader
    yaml_tag = "!CommandTemplate"
    """str: yaml tag to recognise object in yaml file. A yaml file can provide a 
            predefined set of commands. The sets are loaded by the DictCommandItemLib
    """

    def __init__(
        self,
        name,
        description,
        request_object=None,
        command_composition=None,
        answer_analysis=None,
        argument_mappings=None,
    ):

        self.name = name
        self.description = description
        self.request_object = request_object
        self.command_composition = command_composition
        self.answer_analysis = answer_analysis
        self.argument_mappings = argument_mappings

    def __repr__(self):
        return f"Command: {self.name}"

    def __str__(self):
        return self.name

    @property
    def arguments(self):
        return list(self.argument_mappings)

    def argument_type(self, key):
        """get argument type from mapping"""
        mapping = self.argument_mappings[key]
        if isinstance(mapping, list):  # discrete values
            return type(mapping[0])
        elif isinstance(mapping, dict):  # dicrete values with mapping to string
            return type(list(mapping.values())[0])
        elif isinstance(mapping, str):
            if mapping in ["int", "float", "str"]:
                return eval(mapping)
        # else
        raise AttributeError("format no found")

    def cast_argument_as_type(self, key, value):
        return self.argument_type(key)(value)

    def create_arg_dict(self, args):
        """returns a dict with argument description and casted values

        Args:
            args (tuple): arguments to be mapped a casted, must have the same length as
                mapping dict

        """
        d = dict()
        for key, arg in zip(self.argument_mappings.keys(), args):
            d[key] = self.cast_argument_as_type(key, arg)
        return d

    def sorted_tuple_from_dict(self, argument_dict):
        # TODO sort args by dict
        return list(argument_dict.values())


class CommandTemplateList(dict):
    """dict, managing in yaml file predefined options.

    Each Device should be loaded by its own DictCommandItemLib.

    Args:
        file_path (str or pathlib.Path): path of yaml file.
        *args: passed to super (dict)
        **kwargs: passed to super (dict)

    """

    def __init__(self, file_path, *args, **kwargs):
        # dict.__init__(*args, **kwargs)
        self.file_path = pathlib.Path(file_path)
        super().__init__(*args, **kwargs)
        if self.file_path.exists():
            self.load_objects_from_yaml()
        else:
            raise FileNotFoundError()

    def load_objects_from_yaml(self):
        """Loads all command item objects from yaml file to a dict."""
        with open(self.file_path, "r") as infile:
            list_obj = yaml.safe_load(infile)
            for obj in list_obj:
                self.update({obj.name: obj})


def format_arg_count(fmt):
    try:
        names = [
            name
            for text, name, spec, conv in string.Formatter().parse(fmt)
            if name is not None
        ]
        if all(name == "" for name in names):
            # unnumbered fields "{} {}"
            cnt = len(names)
        else:
            # numbered "{0} {1} {2} {0}"
            cnt = 1 + max(int(name) for name in names)
        fmt.format(*range(cnt))
    except Exception as ex:
        logging.getLogger().warning(f"error: {ex}")
        return None  # or raise ValueError(err)
    return cnt


if __name__ == "__main__":

    from viewcontrol.remotecontrol import supported_devices

    devs = supported_devices

    Dev = devs.get("Behringer X32")
    dev = Dev("192.168.178.122", 123)

    print(devs)
