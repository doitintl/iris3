import os


def detect_gae():
    gae_app = os.environ.get("GAE_APPLICATION", "")
    return "~" in gae_app
