import logging
import textwrap
import typing

from util.config_utils import iris_prefix


def cls_by_name(fully_qualified_classname):
    parts = fully_qualified_classname.split(".")
    fully_qualified_module_name = ".".join(parts[:-1])
    module = __import__(fully_qualified_module_name)
    for subcomponent in parts[1:]:
        try:
            module = getattr(module, subcomponent)
        except AttributeError:
            logging.exception(
                f"Cannot load {fully_qualified_classname}. "
                "Plugin classes must have the same name as their module "
                "(file under the plugins directory), except that the "
                "module name should be in lowercase and the class name in Titlecase, "
                "as for example bigquery.Bigquery or gce.Gce.",
                exc_info=True,
            )
            raise
    return module


def shorten(o, length=400) -> str:
    return textwrap.shorten(str(o), length)


def methods(o, pfx="") -> typing.List[typing.Callable]:
    names = (
        name
        for name in dir(o.__class__)
        if callable(getattr(o.__class__, name)) and name.startswith(pfx)
    )
    return [getattr(o, name) for name in names]


def init_logging():
    logging.basicConfig(
        format=f"%(levelname)s [{iris_prefix()}]: %(message)s",
        level=logging.INFO,
    )


def truncate_mid(s, desired_len):
    if len(s) <= desired_len:
        return s

    elipsis = " ... "

    second_half_start = int(desired_len / 2 - len(elipsis))

    first_half_len = desired_len - second_half_start - len(elipsis)
    return f"{s[:first_half_len]}{elipsis}{s[-second_half_start:]}"
