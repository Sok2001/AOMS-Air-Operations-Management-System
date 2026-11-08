"""Sidebar icons (colored PNGs in assets/icons/, created by make_icons.py). Falls back to the old text glyph
if Pillow or a file is missing, so the program always starts."""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "assets", "icons")
_cache = {}


def slug(name):
    return name.lower().replace(" ", "_").replace("/", "_")


def load(name, size=26):
    """CTkImage for a page name ('Air Map' -> assets/icons/air_map.png) or None."""
    key = (name, size)
    if key in _cache:
        return _cache[key]
    img = None
    path = os.path.join(ICON_DIR, slug(name) + ".png")
    try:
        if os.path.exists(path):
            import customtkinter as ctk
            from PIL import Image
            im = Image.open(path).convert("RGBA")
            img = ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))
    except Exception:
        img = None
    _cache[key] = img
    return img
