import logging
import random
import string
import sys
import textwrap
import time
import typing
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache, wraps

import flask

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


def random_str(length: int):
    return "".join(
        random.choices(
            string.ascii_lowercase + string.digits + string.digits,  # more digits
            k=length,
        )
    )


def init_logging():
    class ContextFilter(logging.Filter):
        def filter(self, record):
            try:
                if hasattr(flask.request, "trace_msg"):
                    trace_msg = flask.request.trace_msg
                else:
                    trace_id = flask.request.headers.get(
                        "X-Cloud-Trace-Context", random_str(8)
                    )
                    trace_id_trunc = truncate_middle(trace_id, 20)
                    trace_msg = " [Trace: " + trace_id_trunc + "]"
                    flask.request.trace_msg = trace_msg
            except RuntimeError as e:
                if "outside of request context" in str(e):
                    # Occurs in app tartup
                    trace_msg = ""
                else:
                    raise e

            record.trace_msg = trace_msg
            return True

    f = ContextFilter()

    h1 = logging.StreamHandler(sys.stdout)
    h1.addFilter(filter=f)
    logging.basicConfig(
        handlers=[h1],
        format=f"%(levelname)s [{iris_prefix()}]%(trace_msg)s %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    logging.info("logging: Initialized logger")


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
                if hasattr(args[0], "__name__"):
                    name_base = args[0]
                else:
                    name_base = type(args[0])
                arg_s = name_base.__name__
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


def truncate_middle(s, resulting_len):
    ellipsis_s = "..."
    if len(s) < len(ellipsis_s):
        return s
    len_remaining_strings = resulting_len - len(ellipsis_s)
    half = len_remaining_strings // 2
    len_sfx_string = half
    len_pfx_string = half if len_remaining_strings % 2 == 0 else half + 1
    pfx = s[:len_pfx_string]
    sfx = s[-len_sfx_string:]
    ret = pfx + ellipsis_s + sfx
    assert len(ret) == resulting_len, len(ret)
    return ret
