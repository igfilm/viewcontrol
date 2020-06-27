import inspect
import pathlib
import pkgutil
import os

from ..util.importhelper import load_dir_modules

__all__ = ["supported_devices", "dict_command_folder"]

dict_command_folder = pathlib.Path(__file__).parent.parent.joinpath(
    "data", "remotecontrol"
)


def _get_supported_devices():
    dict_devices = dict()
    for path, modname, ispkg in pkgutil.iter_modules([pathlib.Path(__file__).parent]):
        if ispkg:
            package = f"viewcontrol.remotecontrol.{modname}"
            mods = load_dir_modules(os.path.join(path.path, modname), package)
            for mod in mods:
                clsmembers = inspect.getmembers(mod, inspect.isclass)
                for cls_name, cls_obj in clsmembers:
                    device_name = getattr(cls_obj, "device_name", None)
                    device_type = getattr(cls_obj, "device_type", None)
                    if device_name and device_type:
                        if cls_obj.device_name is not "ThreadCommunicationBase":
                            cls_obj.update_dict_command_template()
                            dict_devices[cls_obj.device_name] = cls_obj
    return dict_devices


supported_devices = _get_supported_devices()
