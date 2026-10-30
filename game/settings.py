import json
import os

PATH = "game_settings.json"

DEFAULT = {
    "light_cull_margin": 32,
    "light_blur": True,
    "vsync": True,
    "show_fps": True,
}


def load():
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(DEFAULT)
        out = dict(DEFAULT)
        out.update(data)
        return out
    except Exception:
        return dict(DEFAULT)


def save(data):
    try:
        with open(PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
