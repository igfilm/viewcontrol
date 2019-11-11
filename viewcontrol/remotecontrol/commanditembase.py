import re
import yaml

class CommandItemBase (yaml.YAMLObject):
    """Stores one sigle command and provides funtions to write and interpretate

    device-specific classes are derived from this class. All command objects
    will be loaded in dict, which is used to populate dropdownlists in the
    GUI and to search for the command/meaning of a recived string.

    There is no input checking since the objects/dicts are only interacted via
    GUI and dropdownlists

    Args:
        name (str): short and easy name of the command (for dropdown list)
        description (str): description of command
        string_requ=None (str): string to request an information without 
            addtional arguments. Eg. status information
        parser_send=None (str): string in python arguments  where the 
            string follows PEP 3101 of str.format() for the arguments
        parser_recv=None (str): regex expresion to extract the information
            from a recived message
        dict_mapping=None (dict): maps command strings as key and their
            meaning. Will also be used for dropdown Menus 

    Attributes:
        self.name (str): see Args
        self.description (str): see Args
        self.string_requ (str): see Args
        self.parser_send (str): see Args
        self.parser_recv (str): see Args
        self.dict_mapping (str): see Args
    """
    
    yaml_tag = u'!CommandItem'
    start_seq=''
    end_seq='\r'
    error_seq=''

    def __init__(self, name, description, 
                 string_requ=None,
                 parser_send=None,
                 parser_recv=None, 
                 dict_mapping=None):
        self.name = name
        self.description = description
        self.string_requ = string_requ
        self.parser_send = parser_send
        self.parser_recv = parser_recv
        self.dict_mapping = dict_mapping
        
    def __repr__(self):
        return "{}|{}|{}|{}|{}|{}".format(
                self.name, 
                self.description,
                self.string_requ,
                self.parser_send,
                self.parser_recv,
                type(self.dict_mapping),
                )

    def get_send_command(self, *args):
        """sends the command stored parser_send with the given parameters
            
        Args:
            *args: Variable length argument list.

        """
        if len(args)==0:
            return self._combine_command(self.parser_send)
        else:
            subcommand=list(args)
        if isinstance(self.dict_mapping, dict):  # auwahl an befehlen
            for i in range(len(subcommand)):
                if subcommand[i] in self.dict_mapping.keys():
                    pass
                elif subcommand[i] in self.dict_mapping.values():
                    for key, val in self.dict_mapping.items():
                        if val == subcommand[i]:
                            subcommand[i] = key
                else:
                    raise ValueError("subcommand '{}' not in dictionary")
            args = tuple(subcommand)
        return self._combine_command(self.parser_send.format(*args))
    
    def get_send_request(self):
        """send the command stored in string_requ"""

        return self._combine_command(self.string_requ)

    def _combine_command(self, str_command):
        """adds the start and end sequence to each commannd string

        Args:
            str_command (str): command to be combined

        Returns:
            str: combined command
        """
        tmp_start_seq = ''
        if not CommandItemBase.start_seq in str_command:
            tmp_start_seq = CommandItemBase.start_seq
        return tmp_start_seq + str_command + CommandItemBase.end_seq
    
    def get_recv_parser(self, recv_str, map=True):
        """Extract value(s) from recv_str using regex expresion in parser_recv
        
        Args:
            recv_str (str): string with information
            map (bool, optional): if true, Map string with dicitonary. 
                Default to True.

        Returns:
            object: return value, usualy str, can also be object when maped
        """

        if recv_str == 'nack':
            return None
        m = re.search(self.parser_recv, recv_str)
        retval = list(m.groups())
        if map and isinstance(self.dict_mapping, dict):
            for i in range(len(retval)):
                retval[i] = self.dict_mapping.get(retval[i])
        return retval
        

    @staticmethod
    def convert2dict(list_commandobj):
        """converts list to dict with name as key and obj as value"""
        dict_commandobj = dict()
        for commandobj in list_commandobj:
            dict_commandobj.update({commandobj.name: commandobj})
        return dict_commandobj

    @staticmethod
    def load_from_yaml(file_path):
        """loads a object dict from yaml file"""
        with open(file_path, 'r') as infile:
            list_commandobj = yaml.load(infile, Loader=yaml.Loader)
        return CommandItemBase.convert2dict(list_commandobj)


class DictCommandItemLib(dict):
    """dict, which provides custom search functions
    """

    def __init__(self, file_path=None, *args, **kwargs):
        # dict.__init__(*args, **kwargs)
        super().__init__(*args, **kwargs)
        if file_path:
            self.load_commands(file_path)

    def load_commands(self, file_path):
        """updates dict with items from given file

        Args:
            file_path(str): path to yaml file containig commands

        """
        self.update(CommandItemBase.load_from_yaml(file_path))

    def get_command_from_answer(self, str_answ):
        """finds the command which can interprate the given string

        Args:
            str_answ: string containing the information

        Returns:
            str: key of command in dictionary
        """
        for key, value in self.items():
            if not isinstance(value.parser_recv, str):
                continue
            m = re.search(value.parser_recv, str_answ)
            if m:
                return key
        return None
    
    def get_full_answer(self, str_answ):
        """return value(s) of interprated string
        
        Args:
            str_answ: string containing information
        
        Returns:
            tuple, str: if found: (key, result as array), 
                         if not found: str with message
        """
        key = self.get_command_from_answer(str_answ)
        if key:
            return (key, self.get(key).get_recv_parser(str_answ))
        else:
            return None