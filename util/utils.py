import logging
import textwrap
import time
import typing

from functools import lru_cache, wraps
from datetime import datetime, timedelta


from contextlib import contextmanager

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
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)


def __log_end_timer(tag, start):
    logging.info(f"Time {tag}: {int((time.time() - start) * 1000)} ms")


def log_time(func):
    @wraps(func)
    def _time_it(*args, **kwargs):
        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            if args:
                arg = args[0]
                arg_s = (
                    arg.__name__
                    if hasattr(arg, "__name__")
                    else type(arg).__name__
                    if args
                    else ""
                )
            else:
                arg_s = ""
            __log_end_timer(f"{func.__name__}({arg_s})", start)

    return _time_it


@contextmanager
def timing(tag: str) -> None:
    start = time.time()
    yield
    elapsed_ms = int((time.time() - start) * 1000)
    logging.getLogger("Time").info("%s: %d ms", tag, elapsed_ms)


def timed_lru_cache(seconds: int, maxsize: int = 128):
    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.utcnow() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.utcnow() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime

            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache
