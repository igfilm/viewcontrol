import logging
import pathlib
import re
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
        delay (float): delay to send signal (handled in ProcessCmd)
        request (bool): true if request object has to be used otherwise
            command_composition string will be used. Defaults to False.

    For Attributes see Arguments. Attributes are identical with arguments.
    """

    def __init__(self, device, command, arguments=(), delay=0, request=True):
        super().__init__(device, command)
        self.arguments = arguments
        self.delay = delay
        self.request = request

    def __str__(self):
        return (
            f"{self.device} -> {self.command} {self.arguments}; request:{self.request}"
        )


class CommandRecvItem:
    """Object holding content of received messages and additional information.

    Args:
        device (str): name representation of device.
        command (str or None): name representation of command.
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
        return (
            f"{self.device} <- {self.command} {self.values}; "
            f"request:{self.message_type}"
        )


class CommandTemplate(yaml.YAMLObject):
    """Stores one single command and provides functions for message handling.

    Arguments are identical to Attributes. See Attributes.

    Attributes:
        name (str): short and easy name of the command (for drop-down list).
        description (str): description of command including parameter description.
        request_composition (obj): object to be send to request something, usually a
            string.
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

    allowed_type_strings = ["int", "float", "str"]

    def __init__(
        self,
        name,
        description,
        request_composition=None,
        command_composition=None,
        answer_analysis=None,
        argument_mappings=None,
    ):

        self.name = name
        self.description = description
        self.request_composition = request_composition
        self.command_composition = command_composition
        self.answer_analysis = answer_analysis
        self.argument_mappings = argument_mappings
        self.__is_valid_err_counter = 0

    def __repr__(self):
        return f"Command: {self.name}"

    def __str__(self):
        return self.name

    @property
    def arguments(self):
        return list(self.argument_mappings)

    @property
    def number_mapping_arguments(self):
        if self.argument_mappings:
            return len(self.argument_mappings)
        return 0

    @property
    def number_command_arguments(self):
        if self.command_composition:
            return format_arg_count(self.command_composition, raise_ex=False)
        return 0

    @property
    def number_request_arguments(self):
        if self.request_composition:
            return format_arg_count(self.request_composition, raise_ex=False)
        return 0

    @property
    def number_analysis_arguments(self):
        if self.answer_analysis:
            return re.compile(self.answer_analysis).groups
        return 0

    def argument_type(self, key):
        """get argument type from mapping for given key

        Returns:
            type:

        """
        mapping = self.argument_mappings[key]
        if isinstance(mapping, list):  # discrete values
            return type(mapping[0])
        elif isinstance(mapping, dict):  # discrete values with mapping to string
            return type(list(mapping.values())[0])
        elif isinstance(mapping, str):
            if mapping in self.allowed_type_strings:
                return eval(mapping)
        # else
        raise AttributeError("format no found")

    def cast_argument_as_type(self, key, value):
        return self.argument_type(key)(value)

    def create_arg_dict(self, args):
        """returns a dict with argument description and casted values.

        Args:
            args (tuple): arguments to be mapped a casted, must have the same length as
                mapping dict

        Returns:
            dict:

        """

        d = dict()

        if len(args) == 0:
            return d

        for key, arg in zip(self.argument_mappings.keys(), args):
            d[key] = self.cast_argument_as_type(key, arg)
        return d

    def sorted_tuple_from_dict(self, argument_dict):
        """Sorts a dict in the order of the argument_mapping, dict must have same keys.

        Returns:
            tuple: arguments in order of dict

        """
        sort = [argument_dict.get(key) for key in self.argument_mappings.keys()]
        return tuple(sort)

    def __print_message(self, rule, attribute, msg):
        self.__is_valid_err_counter += 1
        composed = f"{self.name:<20}{rule:<2} {attribute:<19}: {msg}"
        logging.getLogger().warning(f"YAML Error in loaded Device: {composed}")

    def is_valid(self):
        """Returns 0 if object is valid by checking a list of criteria.

        prints errors into log.

        Returns:
            int: number of errors

        """

        self.__is_valid_err_counter = 0
        prm = self.__print_message

        def try_arg_count_formatter(name, fmt):
            """also a test if formatter string is valid"""
            try:
                return format_arg_count(fmt, raise_ex=True)
            except ValueError as err:
                prm("4", name, f"formatter error: {err}")
                return None

        def try_arg_count_regex(expr):
            try:
                return re.compile(expr).groups
            except re.error as err:
                prm("6", "answer_analysis", f"regex error: {err}")
                return None

        def smaller_equal(a, b):
            if a and b:
                return a <= b
            else:
                return True

        def homogeneous_type(seq):
            iseq = iter(seq)
            first_type = type(next(iseq))
            return first_type if all((type(x) is first_type) for x in iseq) else False

        for att in [
            "name",
            "description",
            "request_composition",
            "command_composition",
            "answer_analysis",
            "argument_mappings",
        ]:
            if not hasattr(self, att):
                prm("1", att, "attribute missing")

        mapping_arg_number = None
        if self.argument_mappings:
            if not all(isinstance(x, str) for x in self.argument_mappings.keys()):
                prm("8a", "argument_mappings", "all dict keys must be of type str")
            for key, value in self.argument_mappings.items():
                if isinstance(value, str):
                    if value not in self.allowed_type_strings:
                        prm(
                            "8b",
                            "argument_mappings",
                            f"str of '{key}' must be in {self.allowed_type_strings}",
                        )
                elif isinstance(value, list):
                    if not homogeneous_type(value):
                        prm(
                            "8b",
                            "argument_mappings",
                            f"all list elements of '{key}' must have the same type",
                        )
                elif isinstance(value, dict):
                    if not homogeneous_type(value.values()):
                        prm(
                            "8b",
                            "argument_mappings",
                            f"all dict values of '{key}' must have the same type",
                        )
                    if not all(isinstance(x, str) for x in value.keys()):
                        prm(
                            "8b",
                            "argument_mappings",
                            f"all dict keys of '{key}' must be of type str",
                        )
                else:
                    prm("8b", "argument_mappings", f"type  of '{key}' is not known")
            mapping_arg_number = len(self.argument_mappings)

        # request_arg_number = None  # 0 if request object exists else None
        if self.request_composition:
            request_arg_number = try_arg_count_formatter(
                "request_composition", self.request_composition
            )

            if not smaller_equal(request_arg_number, mapping_arg_number):
                prm("5", "request_composition", "more formatter's than arguments")

        # command_arg_number = None
        if self.command_composition:
            command_arg_number = try_arg_count_formatter(
                "command_composition", self.command_composition
            )

            if not smaller_equal(command_arg_number, mapping_arg_number):
                prm("5", "command_composition", "more formatter's than arguments")

        analysis_arg_number = None
        if self.answer_analysis:
            analysis_arg_number = try_arg_count_regex(self.answer_analysis)

            if not smaller_equal(analysis_arg_number, mapping_arg_number):
                prm("7", "answer_analysis", "more regex capture groups than arguments")

        if analysis_arg_number is not None and mapping_arg_number is None:
            if analysis_arg_number > 0:
                prm("3", "mapping_arg_number", "answer analysis needs a mapping dict")

        if self.__is_valid_err_counter == 0:
            logging.getLogger().debug(f"command {self.name} isn valid")

        return self.__is_valid_err_counter


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

    def is_valid(self):
        errors = 0
        for command_template in self.values():
            errors += command_template.is_valid()
        return errors


def format_arg_count(fmt, raise_ex=False):
    """return arguments in formatter string, catches errors by default.

    Args:
        fmt(str): formatter string
        raise_ex(bool): if True, don't catch as exceptions. Defaults to False.

    """
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
        if raise_ex:
            raise
        return None  # or raise ValueError(err)
    return cnt
