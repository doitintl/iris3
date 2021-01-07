import logging
import textwrap


def cls_by_name(fully_qualified_classname):
    parts = fully_qualified_classname.split('.')
    fully_qualified_module_name = '.'.join(parts[:-1])
    module = __import__(fully_qualified_module_name)
    for subcomponent in parts[1:]:
        try:
            module = getattr(module, subcomponent)
        except AttributeError:
            logging.exception(
                'Plugin classes must have the same name as their module '
                '(file under the plugins directory), except that the '
                'module name should be in lowercase and the class name in title case,'
                'as for example gce.Gce. Tried to load %s' % fully_qualified_classname,
                exc_info=True)
            raise
    return module


def shorten(o, length=400) -> str:
    return textwrap.shorten(str(o), length)
