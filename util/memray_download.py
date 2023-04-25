import logging
import os

import sys
import time
import urllib.request
from html.parser import HTMLParser
from subprocess import CalledProcessError
from urllib.error import HTTPError
from pathlib import Path
from test_scripts.utils_for_tests import assert_root_path
from util.utils import mkdirs, run_command


def download(base, path):
    if base.endswith("/") and path.startswith("/"): path=path[1:]
    url = base + path
    try:

        with urllib.request.urlopen(url) as f:
            ret = f.read()
            logging.info("downloaded %s", url)
            return ret

    except HTTPError as e:
        logging.error("cannot download %s", url)
        raise e


def download_txt(base, path):
    return download(base, path).decode("utf-8")


class ExtractHrefs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        for attr in attrs:
            if attr[0] == "href":
                self.paths.append(attr[1])


def download_list_and_bins(base):
    html = download_txt(base, "list_memray")
    parser = ExtractHrefs()
    parser.feed(html)
    existing_bin=[Path(p).stem for p in Path(dir_with_bin()).iterdir()]
    for path in parser.paths:
        bin_pth = Path(path)
        exist= bin_pth.stem in existing_bin

        if not exist:
            bin_content = download(base, path)
            filename = bin_pth.name
            mkdirs(dir_with_bin())
            save_path = f"{dir_with_bin()}/{filename}"
            with open(save_path, "wb") as f:
                f.write(bin_content)


def download_and_convert(base):
    assert_root_path()
    download_list_and_bins(base)
    generate_flamegraphs()


def generate_flamegraphs():
    mkdirs(dir_with_html_leaks())
    mkdirs(dir_with_html_basic())

    binfiles = list(filter(lambda filename: filename.endswith(".bin"), os.listdir(dir_with_bin())))
    print(len(binfiles), "bin files in", dir_with_bin())

    for f in binfiles:
        if f.endswith(".bin"):
            stem_for_html = Path(f).stem
            binfn = f"{dir_with_bin()}/{f}"
            sz = os.path.getsize(binfn)
            if sz > 1000:
                convert_bin_to_one_html(binfn, stem_for_html, False, )
                convert_bin_to_one_html(binfn, stem_for_html, True)

    count_html = sum(1 for _ in Path(dir_with_html_basic()).iterdir())
    print(count_html, "html files in", dir_with_html_basic())
    count_html_leak = sum(1 for _ in Path(dir_with_html_leaks()).iterdir())
    print(count_html_leak, "html files in", dir_with_html_leaks())


__memray_dir = "memray"


def dir_with_bin():
    return Path(__memray_dir + "/bin").absolute()


def dir_with_html_basic():
    return Path(__memray_dir + "/html_basic").absolute()


def dir_with_html_leaks():
    return Path(__memray_dir + "/html_leaks").absolute()


def convert_bin_to_one_html(binfn, stem_for_html, leaks):
    dir_html = dir_with_html_leaks() if leaks else dir_with_html_basic()
    abs_output_path = f"{dir_html}/memray-flamegraph-{stem_for_html}.html"
    exists = os.path.isfile(abs_output_path)
    if not exists:
        flag = " --leaks" if leaks else ""
        command = (
            f"python -m memray flamegraph{flag} --output {abs_output_path} {binfn}"
        )
        print(command)
        try:
            run_command(command)
        except CalledProcessError as cpe:
            print(cpe)


def main():
    start = time.time()
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    if not base.endswith("/"):
        base += "/"
    MINUTES = 60
    while time.time() - start < 10 * MINUTES:
        try:
            download_and_convert(base)
        except HTTPError as e:
            logging.error(e)

        print("Will sleep and check again")
        time.sleep(5)


if __name__ == "__main__":
    main()
