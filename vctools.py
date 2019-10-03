import os
import yaml

def read_yaml():

    default_config_path = "config.yaml"
    if os.path.exists(default_config_path):
        with open(default_config_path, 'rt') as f:
            config = yaml.safe_load(f.read())
            #for p in propertys:
            #    return_dict.update({p:config.get(p)})

            if 'media_file_path' in config.keys():
                default_media_path = '../media'
                if not config.get('media_file_path'):
                    config['media_file_path'] = default_media_path
                if not os.path.exists(config['media_file_path']):
                    if not os.path.exists(default_media_path):
                        os.makedirs(default_media_path)
                
            if 'project_folder' in config.keys():
                default_media_path = '../vcproject'
                if not config.get('project_folder'):
                    config['project_folder'] = default_media_path
                if not os.path.exists(config['project_folder']):
                    if not os.path.exists(default_media_path):
                        os.makedirs(default_media_path)

            return config
    else:
        raise FileNotFoundError(
            "Config File {} not found, can't start programm!" \
            .format(os.path.abspath(default_config_path)))

if __name__ == '__main__':

        print(read_yaml().get('media_file_path'))

        print(read_yaml().get(['media_file_path', 'restart_at_error']))