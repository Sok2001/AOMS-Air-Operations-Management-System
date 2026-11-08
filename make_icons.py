"""
Generates the colored sidebar icons  ->  assets/icons/<name>.png   (run:  python make_icons.py)
Every icon = rounded gradient badge + white pictogram (drawn with Pillow, no external files / fonts needed).
The program only LOADS the PNGs (icons.py); this script is needed only to regenerate or change them.
"""
import math
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")
S = 4                      # supersampling
N = 96 * S                 # working canvas (downscaled to 96 px at the end)
W = (255, 255, 255, 255)
YEL = (253, 224, 71, 255)
PALE = (255, 255, 255, 175)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def P(v):                  # 0..100 design space -> pixels
    return v * N / 100.0


def box(*b):
    return [P(v) for v in b]


def pts(lst):
    return [(P(x), P(y)) for x, y in lst]


def star4(cx, cy, ro, ri):
    out = []
    for i in range(8):
        a = math.radians(-90 + i * 45)
        r = ro if i % 2 == 0 else ri
        out.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return out


def line(d, xy, width, fill, round_caps=True):
    d.line(pts(xy), fill=fill, width=int(P(width)), joint="curve")
    if round_caps:
        for x, y in (xy[0], xy[-1]):
            r = width / 2
            d.ellipse(box(x - r, y - r, x + r, y + r), fill=fill)


def cloud(d, fill, grow=0):
    g = grow
    d.ellipse(box(22 - g, 50 - g, 52 + g, 80 + g), fill=fill)
    d.ellipse(box(36 - g, 36 - g, 70 + g, 72 + g), fill=fill)
    d.ellipse(box(58 - g, 46 - g, 86 + g, 76 + g), fill=fill)
    d.rounded_rectangle(box(30 - g, 58 - g, 78 + g, 80 + g), radius=P(10), fill=fill)


# ------------------------------------------------------------------ glyphs  (d = ImageDraw on RGBA layer, hole = badge color)
def g_dashboard(d, hole):
    for b in ((20, 20, 48, 52), (54, 20, 80, 40), (20, 58, 48, 80), (54, 46, 80, 80)):
        d.rounded_rectangle(box(*b), radius=P(6), fill=W)


def g_flights(d, hole):
    lay = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)

    def sc(lst, k=0.84):
        return [(50 + (x - 50) * k, 50 + (y - 50) * k) for x, y in lst]
    ld.polygon(pts(sc([(50, 38), (92, 64), (92, 72), (50, 60), (8, 72), (8, 64)])), fill=W)
    ld.polygon(pts(sc([(50, 72), (68, 88), (68, 94), (50, 87), (32, 94), (32, 88)])), fill=W)
    ld.rounded_rectangle(box(*[50 + (v - 50) * 0.84 for v in (44, 8, 56, 96)]), radius=P(5), fill=W)
    lay = lay.rotate(-45, resample=Image.BICUBIC)
    d._image.alpha_composite(lay)


def g_runways(d, hole):
    d.polygon(pts([(39, 16), (61, 16), (86, 86), (14, 86)]), fill=W)
    for y0, y1, w in ((24, 32, 1.6), (40, 50, 2.2), (58, 70, 3.0)):
        d.rectangle(box(50 - w, y0, 50 + w, y1), fill=hole)
    d.polygon(pts([(37, 16), (39, 16), (14, 86), (12, 86)]), fill=YEL)
    d.polygon(pts([(61, 16), (63, 16), (88, 86), (86, 86)]), fill=YEL)


def g_airport_data(d, hole):
    d.rectangle(box(43, 46, 57, 84), fill=W)
    d.polygon(pts([(30, 26), (70, 26), (78, 46), (22, 46)]), fill=W)
    d.rectangle(box(33, 31, 67, 39), fill=hole)
    d.rectangle(box(39, 17, 61, 25), fill=W)
    d.rectangle(box(50 - 1.2, 8, 50 + 1.2, 17), fill=W)
    d.rounded_rectangle(box(30, 82, 70, 90), radius=P(3), fill=W)


def g_charts(d, hole):
    d.polygon(pts([(12, 27), (35, 20), (35, 75), (12, 82)]), fill=W)
    d.polygon(pts([(38, 20), (62, 27), (62, 82), (38, 75)]), fill=W)
    d.polygon(pts([(65, 27), (88, 20), (88, 75), (65, 82)]), fill=W)
    line(d, [(20, 66), (45, 52), (54, 60), (78, 38)], 4, hole)
    d.ellipse(box(72, 32, 84, 44), fill=YEL)


def g_traffic(d, hole):
    d.polygon(pts([(33, 14), (52, 38), (40, 38), (40, 82), (26, 82), (26, 38), (14, 38)]), fill=W)
    d.polygon(pts([(67, 86), (86, 62), (74, 62), (74, 18), (60, 18), (60, 62), (48, 62)]), fill=YEL)


def g_capacity(d, hole):
    d.arc(box(14, 18, 86, 90), start=180, end=360, fill=W, width=int(P(10)))
    d.arc(box(14, 18, 86, 90), start=300, end=360, fill=YEL, width=int(P(10)))
    line(d, [(50, 56), (68, 36)], 7, W)
    d.ellipse(box(41, 47, 59, 65), fill=W)
    d.ellipse(box(46, 52, 54, 60), fill=hole)
    d.rounded_rectangle(box(18, 74, 82, 80), radius=P(3), fill=W)


def g_atfcm(d, hole):
    d.ellipse(box(16, 16, 84, 84), outline=W, width=int(P(8)))
    line(d, [(50, 50), (50, 30)], 6.5, W)
    line(d, [(50, 50), (65, 59)], 6.5, YEL)
    d.ellipse(box(45, 45, 55, 55), fill=W)
    for a in range(0, 360, 90):
        x, y = 50 + 30 * math.cos(math.radians(a)), 50 + 30 * math.sin(math.radians(a))
        d.ellipse(box(x - 1.8, y - 1.8, x + 1.8, y + 1.8), fill=W)


def g_weather(d, hole):
    for a in range(0, 360, 45):                                   # sun rays
        x0, y0 = 68 + 17 * math.cos(math.radians(a)), 30 + 17 * math.sin(math.radians(a))
        x1, y1 = 68 + 24 * math.cos(math.radians(a)), 30 + 24 * math.sin(math.radians(a))
        line(d, [(x0, y0), (x1, y1)], 3.2, YEL)
    d.ellipse(box(55, 17, 81, 43), fill=YEL)
    cloud(d, hole, grow=3)                                         # outline in badge color
    cloud(d, W)


def g_notam(d, hole):
    d.rounded_rectangle(box(22, 12, 78, 88), radius=P(9), fill=W)
    d.rounded_rectangle(box(45, 26, 55, 58), radius=P(4), fill=hole)
    d.ellipse(box(44, 65, 56, 77), fill=hole)
    d.polygon(pts([(78, 12), (78, 34), (56, 12)]), fill=(255, 255, 255, 0))      # cut corner
    d.polygon(pts([(56, 12), (78, 34), (56, 34)]), fill=(226, 232, 240, 255))    # folded flap


def g_alerts(d, hole):
    d.ellipse(box(30, 16, 70, 58), fill=W)
    d.polygon(pts([(30, 38), (70, 38), (80, 70), (20, 70)]), fill=W)
    d.rounded_rectangle(box(16, 66, 84, 77), radius=P(5), fill=W)
    d.ellipse(box(41, 74, 59, 90), fill=YEL)
    d.ellipse(box(45, 8, 55, 18), fill=W)


def g_air_map(d, hole):
    d.ellipse(box(26, 14, 74, 62), fill=W)
    d.polygon(pts([(29, 48), (71, 48), (50, 90)]), fill=W)
    d.ellipse(box(40, 28, 60, 48), fill=hole)
    d.ellipse(box(26, 82, 74, 92), outline=PALE, width=int(P(2.6)))


def g_ai_support(d, hole):
    d.polygon(pts(star4(44, 56, 36, 8)), fill=W)
    d.polygon(pts(star4(76, 24, 15, 4)), fill=YEL)
    d.polygon(pts(star4(78, 78, 10, 3)), fill=PALE)


def g_reports(d, hole):
    d.rounded_rectangle(box(20, 52, 36, 82), radius=P(4), fill=W)
    d.rounded_rectangle(box(42, 34, 58, 82), radius=P(4), fill=W)
    d.rounded_rectangle(box(64, 16, 80, 82), radius=P(4), fill=YEL)
    d.rounded_rectangle(box(14, 85, 86, 90), radius=P(2.5), fill=W)


def g_live_flights(d, hole):
    d.ellipse(box(14, 14, 86, 86), outline=PALE, width=int(P(4.5)))
    d.ellipse(box(32, 32, 68, 68), outline=PALE, width=int(P(4.5)))
    line(d, [(50, 50), (76, 24)], 5.5, W)
    d.ellipse(box(44, 44, 56, 56), fill=W)
    d.ellipse(box(60, 60, 74, 74), fill=YEL)


def g_users(d, hole):
    d.ellipse(box(60, 20, 80, 40), fill=PALE)
    d.ellipse(box(52, 44, 96, 96), fill=PALE)
    d.ellipse(box(34, 14, 62, 42), fill=hole)                       # separation ring
    d.ellipse(box(23, 40, 77, 96), fill=hole)
    d.ellipse(box(37, 17, 59, 39), fill=W)
    d.ellipse(box(26, 44, 74, 96), fill=W)


def g_logs(d, hole):
    d.rounded_rectangle(box(22, 18, 78, 88), radius=P(8), fill=W)
    d.rounded_rectangle(box(36, 10, 64, 26), radius=P(5), fill=YEL)
    for y, x1 in ((40, 68), (54, 68), (68, 54)):
        d.rounded_rectangle(box(32, y, x1, y + 5.5), radius=P(2.7), fill=hole)


def g_backup(d, hole):
    d.ellipse(box(22, 62, 78, 84), fill=W)
    d.rectangle(box(22, 28, 78, 73), fill=W)
    d.ellipse(box(22, 62, 78, 84), fill=W)
    d.ellipse(box(22, 16, 78, 40), fill=YEL)
    for y in (40, 54):
        d.arc(box(22, y - 4, 78, y + 18), start=0, end=180, fill=hole, width=int(P(3.4)))
    d.arc(box(22, 28, 78, 52), start=0, end=180, fill=hole, width=int(P(3.4)))


# name -> (top color, bottom color, glyph)
ICONS = {
    "dashboard":    ("#4f9cff", "#1d4ed8", g_dashboard),
    "flights":      ("#38bdf8", "#0369a1", g_flights),
    "runways":      ("#fbbf24", "#b45309", g_runways),
    "airport_data": ("#2dd4bf", "#0f766e", g_airport_data),
    "charts":       ("#a78bfa", "#6d28d9", g_charts),
    "traffic":      ("#22d3ee", "#0e7490", g_traffic),
    "capacity":     ("#4ade80", "#15803d", g_capacity),
    "atfcm":        ("#fb923c", "#c2410c", g_atfcm),
    "weather":      ("#60c8ff", "#0369a1", g_weather),
    "notam":        ("#facc15", "#a16207", g_notam),
    "alerts":       ("#f87171", "#b91c1c", g_alerts),
    "air_map":      ("#34d399", "#047857", g_air_map),
    "ai_support":   ("#e879f9", "#a21caf", g_ai_support),
    "reports":      ("#818cf8", "#4338ca", g_reports),
    "live_flights": ("#f472b6", "#be185d", g_live_flights),
    "users":        ("#c084fc", "#7e22ce", g_users),
    "logs":         ("#94a3b8", "#475569", g_logs),
    "backup":       ("#a3e635", "#4d7c0f", g_backup),
}


def badge(c1, c2):
    top, bot = hexrgb(c1), hexrgb(c2)
    grad = Image.new("RGBA", (N, N))
    gd = ImageDraw.Draw(grad)
    for y in range(N):
        t = y / (N - 1)
        gd.line([(0, y), (N, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, N - 1, N - 1], radius=int(N * 0.24), fill=255)
    grad.putalpha(mask)
    # thin light edge on the top for a glossy look
    gloss = Image.new("RGBA", (N, N), (255, 255, 255, 0))
    gl = ImageDraw.Draw(gloss)
    gl.rounded_rectangle([2, 2, N - 3, N - 3], radius=int(N * 0.24), outline=(255, 255, 255, 70), width=max(2, S))
    gloss.putalpha(ImageChops.multiply(gloss.getchannel("A"), mask))
    grad.alpha_composite(gloss)
    return grad


def make(name):
    c1, c2, fn = ICONS[name]
    img = badge(c1, c2)
    glyph = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    gd._image = glyph
    fn(gd, hexrgb(c2) + (255,))
    shadow = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    shadow.putalpha(glyph.getchannel("A").point(lambda a: int(a * 0.28)))
    shadow = ImageChops.offset(shadow, 0, int(N * 0.02)).filter(ImageFilter.GaussianBlur(N * 0.012))
    img.alpha_composite(shadow)
    img.alpha_composite(glyph)
    return img.resize((96, 96), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in ICONS:
        make(n).save(os.path.join(OUT, n + ".png"), optimize=True)
    print(f"{len(ICONS)} icons -> {OUT}")


if __name__ == "__main__":
    main()
