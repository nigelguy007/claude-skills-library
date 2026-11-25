"""Where the pack lives, and a loader for its tools (the skill folders have hyphens, so no plain import)."""

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # the folder that holds the startup-* skill folders
PACK = ["startup-skill", "startup-board", "startup-competitors", "startup-buyers", "startup-marketing", "startup-numbers",
        "startup-plan"]


def skill(name, *parts):
    return os.path.join(ROOT, name, *parts)


def load(skill_name, module):
    path = skill(skill_name, module + ".py")
    spec = importlib.util.spec_from_file_location("startup_pack_" + module, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
