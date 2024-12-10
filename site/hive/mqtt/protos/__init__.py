import pkgutil
import importlib
import os
import sys
from google.protobuf import message

def import_submodules(package, recursive=True):
    """ Import all submodules of a module, recursively, including subpackages

    :param package: package (name or actual module)
    :type package: str | module
    :rtype: dict[str, types.ModuleType]
    """
    if isinstance(package, str):
        package = importlib.import_module(package)
    results = {}
    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + '.' + name
        if is_pkg:
            results[full_name] = importlib.import_module(full_name)
        else:
            try:
                __import__(full_name)
            except:
                print(f"Failed to import {full_name}")
                pass
        if recursive and is_pkg:
            results.update(import_submodules(full_name))
    return results

def get_protos():
    sys.path.append(os.path.dirname(os.path.realpath(__file__)))
    import_submodules("embodied")
    return {cls.DESCRIPTOR.full_name: cls for cls in message.Message.__subclasses__()}

PROTOS = get_protos()
