import re
import yaml

class CommandObj (yaml.YAMLObject):
    
    yaml_tag = u'!CommandObj'
    start_seq=''
    end_seq='\r'

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
        
    def send_command(self, subcommand=None):
        if not subcommand:
            return CommandObj.start_seq \
                + self.parser_send \
                + CommandObj.end_seq
        elif isinstance(self.dict_mapping, dict):  # auwahl an befehlen
            if subcommand in self.dict_mapping.keys():
                pass
            elif subcommand in self.dict_mapping.values():
                for key, val in self.dict_mapping.items():
                    if val == subcommand:
                        subcommand = key
            else:
                raise ValueError("subcommand '{}' not in dictionary")
        return CommandObj.start_seq \
            + self.parser_send.format(subcommand) \
            + CommandObj.end_seq
    
    def send_request(self):
        return CommandObj.start_seq \
            + self.string_requ \
            + CommandObj.end_seq
    
    def recv_parser(self, recv_str):
        if recv_str == 'nack':
            return None
        m = re.search(self.parser_recv, recv_str)
        if isinstance(self.dict_mapping, dict):
            return(self.dict_mapping.get(m.group(1)))
        else:
            return m.group(1)
        return m.group(1)
        

    @staticmethod
    def convert2dict(list_commandobj):
        dict_commandobj = dict()
        for commandobj in list_commandobj:
            dict_commandobj.update({commandobj.name: commandobj})
        return dict_commandobj

    @staticmethod
    def load_from_yaml(file_path):
        with open(file_path, 'r') as infile:
            list_commandobj = yaml.load(infile, Loader=yaml.Loader)
        return CommandObj.convert2dict(list_commandobj)


class dict_commandobj(dict):

    def __init__(self, file_path=None, *args, **kwargs):
        # dict.__init__(*args, **kwargs)
        super(dict_commandobj, self).__init__(*args, **kwargs)
        if file_path:
            self.load_commands(file_path)

    def load_commands(self, file_path):
        self.update(CommandObj.load_from_yaml(file_path))

    def get_command_from_answer(self, str_answ):
        for key, value in self.items():
            if not isinstance(value.parser_recv, str):
                continue
            m = re.search(value.parser_recv, str_answ)
            if m:
                return key
        return None
    
    def get_full_answer(self, str_answ):
        key = self.get_command_from_answer(str_answ)
        if key:
            return (key, self.get(key).recv_parser(str_answ))
        else:
            return "command not found"


class dnc (CommandObj):
    yaml_tag = u'!CommandDenon'
    start_seq=''
    end_seq='\r'

# class atlona (CommandObj):
#     yaml_tag = u'!CommandAtlona'
#     start_seq=''
#     end_seq='\r'