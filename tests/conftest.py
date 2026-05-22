import importlib.util
import os
import sys


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_link_budget():
    return _load_module("link_budget", os.path.join(REPO_ROOT, "tools", "link_budget.py"))


def load_telemetry_to_nostr():
    return _load_module(
        "telemetry_to_nostr",
        os.path.join(REPO_ROOT, "tracker", "ground-station", "nostr_bridge", "telemetry_to_nostr.py"),
    )


def load_ground_station():
    return _load_module(
        "ground_station",
        os.path.join(REPO_ROOT, "tracker", "ground-station", "ground_station.py"),
    )
