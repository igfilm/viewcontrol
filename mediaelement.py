

class MediaElement:
    
    def __init__(self, name, file_path, list_commands=[]):
        self.name = name
        self.file_path = file_path
        if isinstance(list_commands, list):
            self.list_commands = list_commands
        else:
            self.list_commands = [list_commands]

    def __repr__(self):
        return "{}|{}".format(self.name, self.file_path)

class VideoElement(MediaElement):

    def __init__(self, name, file_path, list_commands=None):
        super().__init__(name, file_path, list_commands=list_commands)

class StillElement(MediaElement):
    
    def __init__(self, name, file_path, list_commands=None, display_time=5):
        super().__init__(name, file_path, list_commands=list_commands)
        self.display_time = display_time
    
    def __repr__(self):
        return "{}|{}|{}".format(self.name, self.file_path, self.display_time)



class Command:

    def __init__(self, name, cmd_object, delay=0):
        self.name = name
        self.cmd_object = cmd_object
        self.delay = delay
    