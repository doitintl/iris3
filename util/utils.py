import logging
import pathlib
import random
import string
import subprocess
import sys
import textwrap
import time
import typing
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache, wraps

import flask

from util.config_utils import iris_prefix
from util.detect_gae import detect_gae


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


def random_str(length: int = 4):
    start = __random_str(1, string.ascii_lowercase)
    return start + __random_str(length - 1, string.ascii_lowercase + string.digits * 2)


def random_hex_str(length: int = 10):
    return __random_str(
        length,
        "0123456789abcde",
    )


def __random_str(length, choose_from):
    return "".join(
        random.choices(
            choose_from,
            k=length,
        )
    )


def init_logging():
    class ContextFilter(logging.Filter):
        def filter(self, record):

            record.trace_msg = ""
            record.path = ""

            def get_path():
                record.path = flask.request.path

            def get_or_gen_trace():
                if hasattr(flask.request, "trace_msg"):
                    trace_msg = flask.request.trace_msg
                else:
                    trace_id = flask.request.headers.get(
                        "X-Cloud-Trace-Context", "df" + random_str(28)
                    )
                    trace_id_trunc = truncate_middle(trace_id, 10, elipsis_len=0)
                    trace_msg = "Trace: " + trace_id_trunc
                    flask.request.trace_msg = trace_msg
                record.trace_msg = trace_msg

            for f in get_path, get_or_gen_trace:
                try:
                    f()
                except RuntimeError as e:
                    if "outside of request context" in str(e):
                        pass  # Occurs in app startup
                    else:
                        raise e

            return True

    ctx_fltr = ContextFilter()

    class OneLineExceptionFormatter(logging.Formatter):
        def formatException(self, exc_info):
            fmtr = super(OneLineExceptionFormatter, self)
            return fmtr.formatException(
                exc_info
            )  # or format into one line however you want to

        def format(self, record):
            fmtr = super(OneLineExceptionFormatter, self)
            s = fmtr.format(record)
            s = s.replace("\n", "\\n")
            return s

    fmt_str = f"%(levelname)s; {iris_prefix()}; %(trace_msg)s; %(path)s; %(message)s"
    if detect_gae():
        fmt = OneLineExceptionFormatter(fmt_str)
    else:
        fmt = logging.Formatter(fmt_str)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(filter=ctx_fltr)
    handler.setFormatter(fmt)
    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
    )

    set_log_levels()
    # # logging.info(
    # #     "Initialized logger; config is  %s", get_config_redact_token()
    # )


def set_log_levels():
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("time-wrapper").setLevel(logging.INFO)
    logging.getLogger("time-ctx-mgr").setLevel(logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)


def __log_end_timer(tag, start, logger):
    logging.getLogger(logger).info(
        f"{logger}: {tag}: {int((time.time() - start) * 1000)} ms"
    )


# Function-wrapper; context-mgr below
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

            __log_end_timer(f"{func.__name__}({arg_s})", start, "timing")

    return _time_it


@contextmanager
def timing(tag: str) -> None:
    start = time.time()
    yield
    __log_end_timer(tag, start, "time")


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


def truncate_middle(s, resulting_len, elipsis_len=3):
    ellipsis_s = "." * elipsis_len

    if resulting_len < len(ellipsis_s) + 2:
        # "a...z" is shortest. The "+ 2" is for the starting and ending letters
        return s

    if len(s) <= len(ellipsis_s) + 2:  # Truncate "ab" to "ab"
        return s

    if len(s) <= resulting_len:  # No need to shorten
        return s

    len_remaining_strings = resulting_len - len(ellipsis_s)
    half = len_remaining_strings // 2
    len_sfx_string = half
    len_pfx_string = half if len_remaining_strings % 2 == 0 else half + 1
    pfx = s[:len_pfx_string]
    sfx = s[-len_sfx_string:]
    ret = pfx + ellipsis_s + sfx
    return ret


def to_camel_case(snake_str):
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def dict_to_camelcase(d):
    ret_camel = {to_camel_case(k): v for k, v in d.items()}
    return ret_camel


def symdiff(dict1, dict2):
    set1 = set(dict1.items())
    items = list(dict2.items())

    set2 = set(items)
    return set1 ^ set2


def curr_func() -> str:
    return sys._getframe(1).f_code.co_name


def run_command(command_s):
    assert "  " not in command_s  # double-space diesrupts the split
    command = command_s.split(" ")
    result = subprocess.run(command, stdout=subprocess.PIPE, check=True)
    output = result.stdout.decode("utf-8")
    return output.strip("\n")


def mkdirs(dir_):
    pathlib.Path(dir_).mkdir(parents=True, exist_ok=True)


def sort_dict(d):
    keys = sorted(list(d.keys()))
    sorted_dict = {i: d[i] for i in keys}
    return sorted_dict