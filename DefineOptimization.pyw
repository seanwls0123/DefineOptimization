"""Define Optimization - crosshair studio and gaming optimizer for Windows. Standard library only (no pip)."""
import base64, colorsys, copy, ctypes, json, math, os, re, shutil, string, subprocess, sys, tempfile, threading
import urllib.error, urllib.parse, urllib.request, webbrowser
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
try:
    import winreg
except ImportError:  # not Windows
    winreg = None
from tkinter import font as tkfont

NAME = "Define Optimization"
VERSION = "1.1.0"
# GitHub repo: seanwls0123/DefineOptimization
UPDATE_URL = "https://raw.githubusercontent.com/seanwls0123/DefineOptimization/main/version.json"
# folder name kept from the old name, so saved crosshairs and tweak backups carry over
DIR = os.path.join(os.path.expanduser("~"), ".crosshair_z2")
FILE = os.path.join(DIR, "data.json")
N, CELL = 25, 14         # pixel grid in the editor
OV_SIZE = 260            # size of the on-screen overlay window
WIN_W, WIN_H = 1152, 650
SB_W = 232               # sidebar width
OX, DY = 152, 40         # pages are laid out in a 100..972 x 156..668 box; render() moves them into place

# ---- palette (dark Fluent look) ----
BG, SIDE, CARD, CARD2, INPUT, STROKE = "#1b1b1e", "#232326", "#2a2a2e", "#35353a", "#212124", "#3a3a40"
TEXT, MUTED, DIM, TRACK = "#f3f3f5", "#a3a3ad", "#6e6e78", "#4a4a52"
ACCENT, ON_ACCENT, HERO = "#60cdff", "#00131c", "#183746"
GOOD, WARN, BAD = "#6ccb5f", "#f5c542", "#ff6b6b"
FAM = "Segoe UI"
F_XS, F_S, F_M, F_B = (FAM, -11), (FAM, -12), (FAM, -13), (FAM, -13, "bold")
F_H, F_L, F_BIG = (FAM, -15, "bold"), (FAM, -28, "bold"), (FAM, -34, "bold")

SWATCH = ["#00e5a0", "#ff3b5c", "#ffe600", "#00b8ff", "#ffffff", "#ff7a00", "#b44dff", "#39ff14"]
STYLES = [("Cross", "cross"), ("T-shape", "tcross"), ("Dot", "dot"), ("Circle", "circle"),
          ("Customizable", "advanced"), ("Pixel", "custom")]
SUBS = [("inner", "Inner lines"), ("outer", "Outer lines"), ("cdot", "Center dot"), ("ring", "Ring"),
        ("outl", "Outline")]
NAV = [("SYSTEM", [("dash", "Dashboard", "dashboard"), ("opt", "Optimize", "bolt"),
                   ("start", "Startup", "power"), ("clean", "Cleanup", "trash")]),
       ("GAMING", [("games", "Games", "gamepad"), ("xh", "Crosshair", "crosshair"),
                   ("stretch", "Stretch", "monitor")])]
HEAD = {"dash": ("Dashboard", "Your PC at a glance, and quick actions."),
        "opt": ("Optimize", "Gaming tweaks for Windows. Every change can be undone."),
        "start": ("Startup", "Choose which programs start with Windows."),
        "clean": ("Cleanup", "Free up disk space. Only temporary files are removed."),
        "games": ("Games", "Launch games as any Epic account, without logging in and out."),
        "xh": ("Crosshair", "Design, draw and save your crosshair."),
        "stretch": ("Stretch", "Custom resolutions, with a crosshair that follows.")}
XTABS = [("look", "Appearance"), ("custom", "Customize"), ("draw", "Draw"), ("lib", "Library")]
SCALE_MODES = [("raw", "Stretch with the screen", "Stretched like the rest of the screen"),
               ("shape", "Keep shape", "Un-stretches the width so it stays round"),
               ("size", "Keep size and shape", "Same size and shape as on native res")]
CANDIDATES = [(1024, 768), (1152, 864), (1280, 960), (1280, 1024), (1440, 1080), (1600, 1200), (1280, 800),
              (1680, 1050), (1280, 720), (1600, 900), (1920, 1200), (1920, 1440), (2560, 1920), (1920, 1080)]
DEFAULT_PREFS = dict(scale_mode="size", restore_exit=False, last_w=1280, last_h=960,
                     g_users={}, g_sel=None)


def _group(p, length, off):
    """Settings for one group of crosshair lines (inner or outer)."""
    return {p + "_on": True, p + "_color": "#00e5a0", p + "_len": length, p + "_lenv": length,
            p + "_link": True, p + "_thick": 2, p + "_off": off, p + "_rot": 0,
            p + "_top": True, p + "_bottom": True, p + "_left": True, p + "_right": True}


DEFAULT = dict(style="cross", color="#00e5a0", size=10, thickness=2, gap=4, radius=12, dot=False,
               dot_size=2, outline=True, outline_color="#000000", outline_thick=1, scale=3, pixels={},
               **_group("inner", 6, 3), **_group("outer", 3, 11),
               cdot_on=False, cdot_color="#00e5a0", cdot_size=2, cdot_round=True,
               ring_on=False, ring_color="#00e5a0", ring_radius=16, ring_thick=2)
PRESETS = {
    "Classic": dict(style="cross", size=10, thickness=2, gap=4, dot=False),
    "Dot": dict(style="dot", dot_size=4),
    "Cross + dot": dict(style="cross", size=8, thickness=2, gap=3, dot=True, dot_size=2),
    "T-shape": dict(style="tcross", size=10, thickness=2, gap=3, dot=False),
    "Circle": dict(style="circle", radius=14, thickness=2, dot=True, dot_size=2),
    "Thin precision": dict(style="cross", size=14, thickness=1, gap=6, dot=False),
}
HEX = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")


def norm_hex(t):
    m = HEX.match(str(t).strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower()


def hsv_hex(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def vtuple(v):
    return tuple(int(x) for x in str(v).strip().lstrip("v").split("."))


def check_update():
    """Returns {'version','url'} if a newer version exists, otherwise None."""
    req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": NAME})
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.load(r)
    return d if vtuple(d["version"]) > vtuple(VERSION) else None


def apply_update(url):
    """Downloads the new exe and swaps it in for the running file once the app has closed."""
    exe = sys.executable
    new = exe + ".new"
    req = urllib.request.Request(url, headers={"User-Agent": NAME})
    with urllib.request.urlopen(req, timeout=60) as r, open(new, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
    if os.path.getsize(new) < 100_000:
        os.remove(new)
        raise RuntimeError("The downloaded file is invalid.")
    bat = os.path.join(tempfile.gettempdir(), "cz2_update.bat")
    with open(bat, "w") as f:
        f.write(f'''@echo off
timeout /t 2 /nobreak >nul
for /l %%i in (1,1,20) do (
  move /y "{new}" "{exe}" >nul 2>&1 && goto done
  timeout /t 1 /nobreak >nul
)
:done
start "" "{exe}"
del "%~f0"
''')
    subprocess.Popen(["cmd", "/c", bat], creationflags=0x08000000, close_fds=True)


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    cur = {**copy.deepcopy(DEFAULT), **d.get("current", {})}
    prefs = {**copy.deepcopy(DEFAULT_PREFS), **d.get("prefs", {})}
    return cur, d.get("saved", {}), prefs


def save(cur, saved, prefs):
    try:
        os.makedirs(DIR, exist_ok=True)
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump({"current": cur, "saved": saved, "prefs": prefs}, f)
    except Exception:
        pass


# ---------------------------------------------------------------- screen resolution (Windows)
class DEVMODEW(ctypes.Structure):
    """Win32 DEVMODEW (display variant). The two name fields are raw UTF-16 arrays; we never read them."""
    _fields_ = [("dmDeviceName", ctypes.c_ushort * 32), ("dmSpecVersion", ctypes.c_ushort),
                ("dmDriverVersion", ctypes.c_ushort), ("dmSize", ctypes.c_ushort),
                ("dmDriverExtra", ctypes.c_ushort), ("dmFields", ctypes.c_uint),
                ("dmPositionX", ctypes.c_int), ("dmPositionY", ctypes.c_int),
                ("dmDisplayOrientation", ctypes.c_uint), ("dmDisplayFixedOutput", ctypes.c_uint),
                ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                ("dmFormName", ctypes.c_ushort * 32), ("dmLogPixels", ctypes.c_ushort),
                ("dmBitsPerPel", ctypes.c_uint), ("dmPelsWidth", ctypes.c_uint), ("dmPelsHeight", ctypes.c_uint),
                ("dmDisplayFlags", ctypes.c_uint), ("dmDisplayFrequency", ctypes.c_uint),
                ("dmICMMethod", ctypes.c_uint), ("dmICMIntent", ctypes.c_uint), ("dmMediaType", ctypes.c_uint),
                ("dmDitherType", ctypes.c_uint), ("dmReserved1", ctypes.c_uint), ("dmReserved2", ctypes.c_uint),
                ("dmPanningWidth", ctypes.c_uint), ("dmPanningHeight", ctypes.c_uint)]


DISPLAY_OK = sys.platform == "win32" and ctypes.sizeof(DEVMODEW) == 220


def _dm():
    dm = DEVMODEW()
    dm.dmSize = ctypes.sizeof(DEVMODEW)
    return dm


def _enum(index):
    dm = _dm()
    if not ctypes.windll.user32.EnumDisplaySettingsW(None, index, ctypes.byref(dm)):
        raise OSError("EnumDisplaySettingsW failed")
    return dm


def screen_size():
    """Current size of the primary screen in real pixels, or None if unknown."""
    try:
        u = ctypes.windll.user32
        return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
    except Exception:
        return None


def current_mode():
    dm = _enum(-1)  # ENUM_CURRENT_SETTINGS
    return int(dm.dmPelsWidth), int(dm.dmPelsHeight), int(dm.dmDisplayFrequency)


def registry_mode():
    """The resolution Windows restores by default (what the user normally runs). We never change this."""
    dm = _enum(-2)  # ENUM_REGISTRY_SETTINGS
    return int(dm.dmPelsWidth), int(dm.dmPelsHeight), int(dm.dmDisplayFrequency)


def list_modes():
    out, i, dm = set(), 0, _dm()
    while ctypes.windll.user32.EnumDisplaySettingsW(None, i, ctypes.byref(dm)):
        if dm.dmBitsPerPel >= 24:
            out.add((int(dm.dmPelsWidth), int(dm.dmPelsHeight), int(dm.dmDisplayFrequency)))
        i += 1
    return sorted(out, reverse=True)


def set_mode(w, h, hz=0, test=False):
    """Changes the resolution until the next restart/log-off (not saved). Returns the Windows result code (0 = ok)."""
    dm = _enum(-1)
    dm.dmPelsWidth, dm.dmPelsHeight = int(w), int(h)
    fields = 0x80000 | 0x100000  # DM_PELSWIDTH | DM_PELSHEIGHT
    if hz:
        dm.dmDisplayFrequency = int(hz)
        fields |= 0x400000       # DM_DISPLAYFREQUENCY
    dm.dmFields = fields
    return int(ctypes.windll.user32.ChangeDisplaySettingsExW(None, ctypes.byref(dm), None, 2 if test else 0, None))


def reset_mode():
    """Back to the resolution stored in Windows settings."""
    return int(ctypes.windll.user32.ChangeDisplaySettingsExW(None, None, None, 0, None))


def ratio(w, h):
    for name, r in (("4:3", 4 / 3), ("5:4", 5 / 4), ("16:10", 1.6), ("16:9", 16 / 9), ("3:2", 1.5), ("21:9", 64 / 27)):
        if abs(w / h - r) < 0.02:
            return name
    g = math.gcd(w, h)
    return f"{w // g}:{h // g}"


def scale_factors(mode, cur, nat):
    """How much to scale the overlay (x, y) so the crosshair looks right on a stretched resolution."""
    (cw, ch), (nw, nh) = cur, nat
    if not (cw and ch and nw and nh):
        return 1.0, 1.0
    if mode == "size":    # same on-screen size and shape as at native resolution
        return cw / nw, ch / nh
    if mode == "shape":   # only undo the stretch so circles stay round
        return (nh * cw) / (ch * nw), 1.0
    return 1.0, 1.0


# ---------------------------------------------------------------- crosshair drawing
def seg_pts(cx, cy, side, off, length, t, rot, grow):
    """Corner points of one crosshair line. `side` is top/bottom/left/right, `rot` is degrees."""
    base = {"right": 0, "bottom": 90, "left": 180, "top": 270}[side]
    a = math.radians(base + rot)
    ca, sa = math.cos(a), math.sin(a)
    v0 = -(t // 2)
    v1 = v0 + t
    u0, u1 = off - grow, off + length + grow
    return [(cx + u * ca - v * sa, cy + u * sa + v * ca)
            for u, v in ((u0, v0 - grow), (u1, v0 - grow), (u1, v1 + grow), (u0, v1 + grow))]


def draw_item(cv, it, tag):
    kind = it[0]
    if kind == "p":                      # line segment (rectangle or rotated polygon)
        _, pts, col, rot = it
        if rot % 90 == 0:
            xs, ys = [round(p[0]) for p in pts], [round(p[1]) for p in pts]
            cv.create_rectangle(min(xs), min(ys), max(xs), max(ys), fill=col, outline="", tags=tag)
        else:
            cv.create_polygon([c for p in pts for c in p], fill=col, outline="", tags=tag)
    elif kind == "o":                    # round dot
        cv.create_oval(*it[1], fill=it[2], outline="", tags=tag)
    elif kind == "s":                    # square dot
        cv.create_rectangle(*it[1], fill=it[2], outline="", tags=tag)
    elif kind == "r":                    # ring
        _, cx, cy, r, w, col = it
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=w, tags=tag)


def draw(cv, cx, cy, s, tag="xh"):
    """Draws the crosshair centered on (cx, cy) using canvas items tagged `tag`."""
    cv.delete(tag)
    col, oc = s["color"], s["outline_color"]
    t, g, L, st = int(s["thickness"]), int(s["gap"]), int(s["size"]), s["style"]
    ot = int(s.get("outline_thick", 1)) if s["outline"] else 0

    if st == "custom":
        ps = int(s["scale"])
        x0, y0 = cx - N * ps // 2, cy - N * ps // 2
        cells = []
        for k, v in s["pixels"].items():
            i, j = map(int, k.split(","))
            cells.append((x0 + i * ps, y0 + j * ps, x0 + (i + 1) * ps, y0 + (j + 1) * ps, v))
        if ot:
            for a, b, c, d, _ in cells:
                cv.create_rectangle(a - ot, b - ot, c + ot, d + ot, fill=oc, outline="", tags=tag)
        for a, b, c, d, v in cells:
            cv.create_rectangle(a, b, c, d, fill=v, outline="", tags=tag)
        return

    if st == "advanced":
        outl, fills = [], []
        for gname in ("inner", "outer"):
            if not s[gname + "_on"]:
                continue
            th, off, rot = int(s[gname + "_thick"]), int(s[gname + "_off"]), int(s[gname + "_rot"])
            for side in ("top", "bottom", "left", "right"):
                if not s[gname + "_" + side]:
                    continue
                ln = int(s[gname + ("_len" if side in ("left", "right") else "_lenv")])
                if ln <= 0:
                    continue
                fills.append(("p", seg_pts(cx, cy, side, off, ln, th, rot, 0), s[gname + "_color"], rot))
                if ot:
                    outl.append(("p", seg_pts(cx, cy, side, off, ln, th, rot, ot), oc, rot))
        if s["cdot_on"]:
            d = int(s["cdot_size"])
            kind = "o" if s["cdot_round"] else "s"
            fills.append((kind, (cx - d, cy - d, cx + d, cy + d), s["cdot_color"]))
            if ot:
                outl.append((kind, (cx - d - ot, cy - d - ot, cx + d + ot, cy + d + ot), oc))
        if s["ring_on"]:
            r, rt = int(s["ring_radius"]), int(s["ring_thick"])
            fills.append(("r", cx, cy, r, rt, s["ring_color"]))
            if ot:
                outl.append(("r", cx, cy, r, rt + 2 * ot, oc))
        for it in outl + fills:
            draw_item(cv, it, tag)
        return

    h = t // 2
    rects, ovals = [], []
    if st in ("cross", "tcross"):
        rects += [(cx - g - L, cy - h, cx - g, cy - h + t), (cx + g, cy - h, cx + g + L, cy - h + t),
                  (cx - h, cy + g, cx - h + t, cy + g + L)]
        if st == "cross":
            rects.append((cx - h, cy - g - L, cx - h + t, cy - g))
    if st == "dot":
        d = int(s["dot_size"])
        ovals.append((cx - d, cy - d, cx + d, cy + d))
    if st in ("cross", "tcross", "circle") and s["dot"]:
        d = int(s["dot_size"])
        ovals.append((cx - d, cy - d, cx + d, cy + d))
    if st == "circle":
        r = int(s["radius"])
        if ot:
            cv.create_oval(cx - r - ot, cy - r - ot, cx + r + ot, cy + r + ot, outline=oc, width=t + 2 * ot, tags=tag)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=t, tags=tag)

    if ot:
        for a, b, c, d in rects:
            cv.create_rectangle(a - ot, b - ot, c + ot, d + ot, fill=oc, outline="", tags=tag)
        for a, b, c, d in ovals:
            cv.create_oval(a - ot, b - ot, c + ot, d + ot, fill=oc, outline="", tags=tag)
    for a, b, c, d in rects:
        cv.create_rectangle(a, b, c, d, fill=col, outline="", tags=tag)
    for a, b, c, d in ovals:
        cv.create_oval(a, b, c, d, fill=col, outline="", tags=tag)


_FONTS = {}


def tw(text, font):
    """Width of `text` in pixels."""
    try:
        f = _FONTS.get(font)
        if f is None:
            f = _FONTS[font] = tkfont.Font(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")
        return f.measure(text)
    except Exception:
        return int(len(text) * abs(font[1]) * 0.55)




def rrect(cv, x0, y0, x1, y1, r, fill, tags="ui", outline="", width=1):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x0 + r, y0, x1 - r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y0 + r, x1, y1 - r, x1, y1 - r,
           x1, y1, x1 - r, y1, x1 - r, y1, x0 + r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y1 - r, x0, y0 + r,
           x0, y0 + r, x0, y0]
    return cv.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=width, tags=tags)


def text(cv, x, y, s, fill=TEXT, font=F_M, anchor="w", tags="ui"):
    return cv.create_text(x, y, text=s, fill=fill, font=font, anchor=anchor, tags=tags)


def icon(cv, name, cx, cy, col, tags="ui"):
    kw = dict(fill=col, width=2, capstyle="round", tags=tags)
    ok = dict(outline=col, width=2, tags=tags)
    if name == "crosshair":
        cv.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, **ok)
        for a, b, c, d in ((-11, 0, -5, 0), (5, 0, 11, 0), (0, -11, 0, -5), (0, 5, 0, 11)):
            cv.create_line(cx + a, cy + b, cx + c, cy + d, **kw)
    elif name == "monitor":
        cv.create_rectangle(cx - 10, cy - 8, cx + 10, cy + 4, **ok)
        cv.create_line(cx, cy + 4, cx, cy + 9, **kw)
        cv.create_line(cx - 5, cy + 9, cx + 5, cy + 9, **kw)
    elif name == "bolt":
        cv.create_polygon([cx + 3, cy - 10, cx - 6, cy + 2, cx - 1, cy + 2, cx - 3, cy + 10, cx + 6, cy - 3, cx + 1, cy - 3],
                          fill="", outline=col, width=2, joinstyle="round", tags=tags)
    elif name == "dashboard":
        for dx, dy in ((-9, -9), (1, -9), (-9, 1), (1, 1)):
            cv.create_rectangle(cx + dx, cy + dy, cx + dx + 8, cy + dy + 8, **ok)
    elif name == "power":
        cv.create_arc(cx - 8, cy - 7, cx + 8, cy + 9, start=120, extent=300, style="arc", outline=col, width=2,
                      tags=tags)
        cv.create_line(cx, cy - 10, cx, cy, **kw)
    elif name == "trash":
        cv.create_line(cx - 8, cy - 6, cx + 8, cy - 6, **kw)
        cv.create_line(cx - 3, cy - 9, cx + 3, cy - 9, **kw)
        cv.create_polygon([cx - 6, cy - 4, cx + 6, cy - 4, cx + 5, cy + 9, cx - 5, cy + 9], fill="", outline=col,
                          width=2, joinstyle="round", tags=tags)
    elif name == "refresh":
        cv.create_arc(cx - 8, cy - 8, cx + 8, cy + 8, start=60, extent=270, style="arc", outline=col, width=2,
                      tags=tags)
        cv.create_polygon([cx + 9, cy - 9, cx + 9, cy - 1, cx + 1, cy - 4], fill=col, outline=col, tags=tags)
    elif name == "shield":
        cv.create_polygon([cx, cy - 10, cx + 8, cy - 6, cx + 7, cy + 3, cx, cy + 10, cx - 7, cy + 3, cx - 8, cy - 6],
                          fill="", outline=col, width=2, joinstyle="round", tags=tags)
    elif name == "check":
        cv.create_line(cx - 6, cy, cx - 2, cy + 5, cx + 6, cy - 5, **kw)
    elif name == "arrow":
        cv.create_line(cx - 5, cy + 5, cx + 5, cy - 5, **kw)
        cv.create_line(cx - 2, cy - 5, cx + 5, cy - 5, cx + 5, cy + 2, **kw)
    elif name == "plus":
        cv.create_line(cx - 6, cy, cx + 6, cy, **kw)
        cv.create_line(cx, cy - 6, cx, cy + 6, **kw)
    elif name == "gamepad":
        cv.create_polygon([cx - 10, cy - 4, cx - 7, cy - 7, cx + 7, cy - 7, cx + 10, cy - 4, cx + 10, cy + 5,
                           cx + 7, cy + 8, cx + 4, cy + 5, cx - 4, cy + 5, cx - 7, cy + 8, cx - 10, cy + 5],
                          fill="", outline=col, width=2, joinstyle="round", tags=tags)
        cv.create_line(cx - 7, cy - 1, cx - 3, cy - 1, **kw)
        cv.create_line(cx - 5, cy - 3, cx - 5, cy + 1, **kw)
        cv.create_oval(cx + 4, cy - 2, cx + 6, cy, fill=col, outline="", tags=tags)


class Surface:
    """Hit-testing for things drawn on a canvas: buttons, sliders, toggles..."""

    def __init__(self, cv):
        self.cv, self.items, self.active = cv, [], None
        cv.bind("<Button-1>", self.down)
        cv.bind("<B1-Motion>", self.move)
        cv.bind("<ButtonRelease-1>", self.up)
        cv.bind("<Motion>", self.hover)
        cv.bind("<MouseWheel>", self.wheel)

    def clear(self):
        self.items = []

    def add(self, box, click=None, drag=None, wheel=None, cursor="hand2"):
        self.items.append(dict(box=box, click=click, drag=drag, wheel=wheel, cursor=cursor))

    def at(self, x, y, need=("click", "drag")):
        for it in reversed(self.items):
            x0, y0, x1, y1 = it["box"]
            if x0 <= x <= x1 and y0 <= y <= y1 and any(it[k] for k in need):
                return it
        return None

    def down(self, e):
        self.cv.focus_set()
        self.active = it = self.at(e.x, e.y)
        if it and it["click"]:
            it["click"](e.x, e.y)

    def move(self, e):
        if self.active and self.active["drag"]:
            self.active["drag"](e.x, e.y)

    def up(self, e):
        self.active = None

    def hover(self, e):
        it = self.at(e.x, e.y)
        try:
            self.cv.config(cursor=it["cursor"] if it else "")
        except Exception:
            pass

    def wheel(self, e):
        it = self.at(e.x, e.y, ("wheel",))
        if it:
            it["wheel"](e.delta)



def btn(cv, sf, x0, y0, x1, y1, label, fn, kind="sec", font=F_B, ic=None):
    """Fluent-style button. kind: pri (accent), sec (neutral), danger."""
    if kind == "pri":
        fill, fg, ol = ACCENT, ON_ACCENT, ""
    elif kind == "danger":
        fill, fg, ol = "#5a2328", "#ffb3b3", ""
    else:
        fill, fg, ol = CARD2, TEXT, STROKE
    rrect(cv, x0, y0, x1, y1, 6, fill, outline=ol)
    cy = (y0 + y1) / 2
    if ic:
        text(cv, (x0 + x1) / 2 + 10, cy, label, fg, font, "center")
        icon(cv, ic, x0 + 22, cy, fg)
    else:
        text(cv, (x0 + x1) / 2, cy, label, fg, font, "center")
    sf.add((x0, y0, x1, y1), click=lambda px, py: fn())


def switch(cv, sf, x, y, on, fn):
    """Fluent toggle switch, 40x20, top-left at (x, y)."""
    if on:
        rrect(cv, x, y, x + 40, y + 20, 10, ACCENT)
        kx, kc, kr = x + 29, ON_ACCENT, 6
    else:
        rrect(cv, x, y, x + 40, y + 20, 10, "", outline="#9a9aa4", width=1)
        kx, kc, kr = x + 11, "#c8c8d0", 5
    cv.create_oval(kx - kr, y + 10 - kr, kx + kr, y + 10 + kr, fill=kc, outline="", tags="ui")
    sf.add((x - 4, y - 4, x + 44, y + 24), click=lambda px, py: fn())


def toggle(cv, sf, x, y, label, on, fn, fg=TEXT):
    """Switch with a label to its right. Returns the total width used."""
    switch(cv, sf, x, y + 1, on, fn)
    text(cv, x + 50, y + 11, label, fg, F_M)
    w = 50 + tw(label, F_M)
    sf.add((x, y - 3, x + w, y + 25), click=lambda px, py: fn())
    return w


def slider(cv, sf, x, y, w, val, lo, hi, fn):
    """Slider; track spans x..x+w at height y."""
    t = (val - lo) / max(hi - lo, 1)
    fx = x + t * w
    rrect(cv, x, y - 2, x + w, y + 2, 2, TRACK)
    rrect(cv, x, y - 2, max(fx, x + 4), y + 2, 2, ACCENT)
    cv.create_oval(fx - 9, y - 9, fx + 9, y + 9, fill="#e9e9ee", outline="", tags="ui")
    cv.create_oval(fx - 5, y - 5, fx + 5, y + 5, fill=ACCENT, outline="", tags="ui")

    def setv(px, py):
        fn(lo + round(min(max((px - x) / w, 0), 1) * (hi - lo)))

    sf.add((x - 10, y - 13, x + w + 10, y + 13), click=setv, drag=setv)


def dark_title(win):
    """Dark title bar on Windows 10/11 (silently ignored elsewhere)."""
    try:
        win.update_idletasks()
        u = ctypes.windll.user32
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        v = ctypes.c_int(1)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4) == 0:
                break
    except Exception:
        pass


# ---------------------------------------------------------------- color wheel
def make_wheel(master, D, bg):
    """Hue/saturation disc as a PhotoImage (full brightness)."""
    img = tk.PhotoImage(master=master, width=D, height=D)
    R = D / 2 - 1
    rows = []
    for y in range(D):
        row = []
        for x in range(D):
            dx, dy = x + 0.5 - D / 2, y + 0.5 - D / 2
            d = math.hypot(dx, dy)
            row.append(bg if d > R else hsv_hex((math.atan2(-dy, dx) / (2 * math.pi)) % 1.0, d / R, 1.0))
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    return img


def center_window(win, w, h):
    ss = screen_size() or (win.winfo_screenwidth(), win.winfo_screenheight())
    win.geometry(f"{w}x{h}+{max((ss[0] - w) // 2, 0)}+{max((ss[1] - h) // 2, 0)}")


class ColorDialog(tk.Toplevel):
    """Color wheel: pick hue/saturation on the wheel, brightness on the bar, or type a hex code."""
    D, W, H = 220, 320, 340
    wheel = None

    def __init__(self, parent, initial, title, live=None):
        super().__init__(parent, bg=CARD)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.live, self.result, self.closed = live, None, False
        self.orig = norm_hex(initial) or "#00e5a0"
        r, g, b = (int(self.orig[i:i + 2], 16) / 255 for i in (1, 3, 5))
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r, g, b)
        D = self.D
        self.R = D / 2 - 1
        if ColorDialog.wheel is None:
            ColorDialog.wheel = make_wheel(parent, D, CARD)
        self.cv = tk.Canvas(self, width=self.W, height=self.H, bg=CARD, highlightthickness=0)
        self.cv.pack()
        self.sf = Surface(self.cv)
        cv = self.cv
        cv.create_image(20, 20, image=ColorDialog.wheel, anchor="nw")
        self.mk1 = cv.create_oval(0, 0, 0, 0, outline="#000000", width=1)
        self.mk2 = cv.create_oval(0, 0, 0, 0, outline="#ffffff", width=2)
        self.vl = [cv.create_line(256, 20 + y, 282, 20 + y) for y in range(D)]
        self.vm = cv.create_rectangle(0, 0, 0, 0, outline=TEXT, width=2)
        text(cv, 20, 254, "NEW", MUTED, F_XS)
        text(cv, 96, 254, "ORIGINAL", MUTED, F_XS)
        self.new = rrect(cv, 20, 266, 90, 292, 13, self.orig)
        rrect(cv, 96, 266, 166, 292, 13, self.orig)
        self.hv = tk.StringVar()
        rrect(cv, 178, 264, 300, 294, 6, INPUT, outline=STROKE)
        ent = tk.Entry(self, textvariable=self.hv, width=9, font=("Consolas", 11), bg=INPUT, fg=TEXT,
                       insertbackground=TEXT, relief="flat", justify="center", highlightthickness=0)
        cv.create_window(190, 268, window=ent, anchor="nw", width=98, height=22)
        ent.bind("<Return>", lambda e: self.from_hex())
        ent.bind("<FocusOut>", lambda e: self.from_hex())
        btn(cv, self.sf, 20, 304, 156, 334, "OK", self.ok, "pri")
        btn(cv, self.sf, 164, 304, 300, 334, "Cancel", self.cancel)
        self.sf.add((96, 266, 166, 292), click=lambda x, y: self.set_hex(self.orig))
        self.sf.add((20, 20, 240, 240), click=self.on_wheel, drag=self.on_wheel, cursor="crosshair")
        self.sf.add((256, 20, 282, 240), click=self.on_val, drag=self.on_val, cursor="sb_v_double_arrow")
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())
        self.update_all(live=False)
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - self.W) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - self.H) // 2
            self.geometry(f"{self.W}x{self.H}+{max(px, 0)}+{max(py, 0)}")
            dark_title(self)
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def on_wheel(self, x, y):
        dx, dy = x - 20 - self.D / 2, y - 20 - self.D / 2
        self.h = (math.atan2(-dy, dx) / (2 * math.pi)) % 1.0
        self.s = min(math.hypot(dx, dy), self.R) / self.R
        self.update_all()

    def on_val(self, x, y):
        self.v = 1 - min(max(y - 20, 0), self.D - 1) / (self.D - 1)
        self.update_all()

    def set_hex(self, hexc):
        r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
        self.h, self.s, self.v = colorsys.rgb_to_hsv(r, g, b)
        self.update_all()

    def from_hex(self):
        if self.closed:
            return
        c = norm_hex(self.hv.get())
        if c and c != self.cur:
            self.set_hex(c)
        elif not c:
            self.hv.set(self.cur.upper())

    def update_all(self, live=True):
        D, cv = self.D, self.cv
        self.cur = hsv_hex(self.h, self.s, self.v)
        cv.itemconfig(self.new, fill=self.cur)
        self.hv.set(self.cur.upper())
        ang = 2 * math.pi * self.h
        x = 20 + D / 2 + self.s * self.R * math.cos(ang)
        y = 20 + D / 2 - self.s * self.R * math.sin(ang)
        cv.coords(self.mk1, x - 7, y - 7, x + 7, y + 7)
        cv.coords(self.mk2, x - 6, y - 6, x + 6, y + 6)
        for yy, line in enumerate(self.vl):
            cv.itemconfig(line, fill=hsv_hex(self.h, self.s, 1 - yy / (D - 1)))
        yv = 20 + (1 - self.v) * (D - 1)
        cv.coords(self.vm, 254, yv - 3, 284, yv + 3)
        if live and self.live:
            self.live(self.cur)

    def ok(self):
        self.closed = True
        self.result = self.cur
        self.destroy()

    def cancel(self):
        self.closed = True
        if self.live:
            self.live(self.orig)
        self.destroy()


def ask_color(parent, initial, title, live=None):
    d = ColorDialog(parent, initial, title, live)
    parent.wait_window(d)
    return d.result


class KeepDialog(tk.Toplevel):
    """'Keep this resolution?' with a countdown; reverts automatically so you can't get stuck on a bad mode."""
    W, H, SECONDS = 360, 170, 10

    def __init__(self, parent, text_new, text_old):
        super().__init__(parent, bg=CARD)
        self.title(NAME)
        self.resizable(False, False)
        self.transient(parent)
        self.keep, self.left, self.closed, self.job = False, self.SECONDS, False, None
        self.old = text_old
        self.cv = tk.Canvas(self, width=self.W, height=self.H, bg=CARD, highlightthickness=0)
        self.cv.pack()
        self.sf = Surface(self.cv)
        text(self.cv, 24, 30, "Keep this resolution?", TEXT, F_H)
        text(self.cv, 24, 58, f"Now: {text_new}", TEXT, F_M)
        self.msg = text(self.cv, 24, 82, "", MUTED, F_S)
        btn(self.cv, self.sf, 24, 112, 170, 148, "Keep", self.ok, "pri")
        btn(self.cv, self.sf, 180, 112, 336, 148, "Revert now", self.cancel)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        center_window(self, self.W, self.H)
        dark_title(self)
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.tick()

    def tick(self):
        if self.closed:
            return
        if self.left <= 0:
            self.cancel()
            return
        self.cv.itemconfig(self.msg, text=f"Reverting to {self.old} in {self.left} s if you do nothing.")
        self.left -= 1
        self.job = self.after(1000, self.tick)

    def stop(self):
        self.closed = True
        try:
            self.after_cancel(self.job)
        except Exception:
            pass
        self.destroy()

    def ok(self):
        self.keep = True
        self.stop()

    def cancel(self):
        self.stop()




class MsgDialog(tk.Toplevel):
    """Dark replacement for message boxes and the small text prompt."""
    W = 420

    def __init__(self, parent, msg, title=None, ask=False, entry=False, yes="OK", no="Cancel", initial=""):
        super().__init__(parent, bg=CARD)
        self.title(NAME)
        self.resizable(False, False)
        self.transient(parent)
        self.result, self.closed, self.entry = None, False, entry
        lines = []
        for para in str(msg).split("\n"):
            cur = ""
            for word in para.split(" "):
                t = (cur + " " + word).strip()
                if cur and tw(t, F_M) > self.W - 48:
                    lines.append(cur)
                    cur = word
                else:
                    cur = t
            lines.append(cur)
        y0 = 54 if title else 32
        h = y0 + len(lines) * 20 + (48 if entry else 0) + 72
        W = self.W
        self.cv = tk.Canvas(self, width=W, height=h, bg=CARD, highlightthickness=0)
        self.cv.pack()
        self.sf = Surface(self.cv)
        cv = self.cv
        if title:
            text(cv, 24, 30, title, TEXT, F_H)
        for i, ln in enumerate(lines):
            text(cv, 24, y0 + i * 20, ln, TEXT if not title else MUTED, F_M)
        if entry:
            ey = y0 + len(lines) * 20 + 4
            rrect(cv, 24, ey, W - 24, ey + 34, 6, INPUT, outline=STROKE)
            self.var = tk.StringVar(value=initial)
            ent = tk.Entry(self, textvariable=self.var, font=(FAM, -14), bg=INPUT, fg=TEXT, insertbackground=TEXT,
                           relief="flat", highlightthickness=0, bd=0)
            cv.create_window(34, ey + 7, window=ent, anchor="nw", width=W - 68, height=20)
            ent.bind("<Return>", lambda e: self.ok())
            ent.focus_set()
        by = h - 58
        if ask:
            btn(cv, self.sf, W - 24 - 112, by, W - 24, by + 34, no, self.cancel, "sec")
            btn(cv, self.sf, W - 24 - 112 - 8 - 120, by, W - 24 - 120, by + 34, yes, self.ok, "pri")
        else:
            btn(cv, self.sf, W - 24 - 112, by, W - 24, by + 34, yes, self.ok, "pri")
            self.bind("<Return>", lambda e: self.ok())
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() - W) // 2
            py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
            self.geometry(f"{W}x{h}+{max(px, 0)}+{max(py, 0)}")
            dark_title(self)
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def ok(self):
        self.result = self.var.get() if self.entry else True
        self.destroy()

    def cancel(self):
        self.result = None if self.entry else False
        self.destroy()


def ask_yes(parent, msg, yes="Yes", no="Cancel"):
    d = MsgDialog(parent, msg, ask=True, yes=yes, no=no)
    parent.wait_window(d)
    return bool(d.result)


def show_msg(parent, msg, title=None):
    d = MsgDialog(parent, msg, title=title)
    parent.wait_window(d)


def ask_text(parent, prompt, initial=""):
    d = MsgDialog(parent, prompt, ask=True, entry=True, yes="Save", no="Cancel", initial=initial)
    parent.wait_window(d)
    return d.result


class messagebox:   # same calls as tkinter.messagebox, but themed
    @staticmethod
    def showerror(title, msg, parent=None):
        show_msg(parent, msg, "Something went wrong")

    @staticmethod
    def showinfo(title, msg, parent=None):
        show_msg(parent, msg)

    @staticmethod
    def askyesno(title, msg, parent=None):
        return ask_yes(parent, msg)


class simpledialog:
    @staticmethod
    def askstring(title, prompt, parent=None):
        return ask_text(parent, prompt)


# ---------------------------------------------------------------- PC optimizer engine (Windows)
# Every tweak is reversible: the original values are saved in prefs["opt_bak"] before anything is changed.
WIN = sys.platform == "win32"
HIVES = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE} if winreg else {}
_RT, _RN = {"d": 4, "s": 1, "b": 3}, {4: "d", 1: "s", 3: "b"}   # REG_DWORD / REG_SZ / REG_BINARY
OPT_CATS = [("game", "Gaming"), ("sys", "System"), ("net", "Network"), ("priv", "Privacy")]
OPT_PROFILES = [("safe", "Safe", "Low risk. Only tweaks with no downside."),
                ("bal", "Balanced", "Recommended for most gaming PCs."),
                ("max", "Max", "Everything except SSD-only tweaks.")]
SAFE_IDS = {"gamemode", "dvr", "mouse", "sticky", "windowed", "anim", "sdelay", "bgapps", "tips", "adid", "deliv"}
OPT_HINT = {"game": "Pick a tweak on or off. Everything can be undone.",
            "sys": "Pick a tweak on or off. Everything can be undone.",
            "net": "Pick a tweak on or off. Everything can be undone.",
            "priv": "Pick a tweak on or off. Everything can be undone.",
            "clean": "Cleanup only removes temporary files.",
            "start": "Programs that start with Windows. Turn off what you don't need."}


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_admin():
    """Restarts this app with administrator rights (UAC prompt). True if Windows accepted it."""
    try:
        if getattr(sys, "frozen", False):
            exe, args = sys.executable, ""
        else:
            exe = sys.executable
            pw = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(pw):
                exe = pw
            args = f'"{os.path.abspath(sys.argv[0])}"'
        return ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1) > 32
    except Exception:
        return False


def run(cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout,
                       creationflags=0x08000000)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def fit(s, font, w):
    """Shortens `s` with ... so it fits in w pixels."""
    if tw(s, font) <= w:
        return s
    while s and tw(s + "...", font) > w:
        s = s[:-1]
    return s.rstrip() + "..."


# ---- registry helpers
def _open(hive, path, write=False):
    return winreg.OpenKey(HIVES[hive], path, 0, (winreg.KEY_SET_VALUE if write else winreg.KEY_READ)
                          | winreg.KEY_WOW64_64KEY)


def rget(hive, path, name):
    try:
        with _open(hive, path) as k:
            return winreg.QueryValueEx(k, name)
    except OSError:
        return None


def rset(hive, path, name, typ, val):
    with winreg.CreateKeyEx(HIVES[hive], path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as k:
        winreg.SetValueEx(k, name, 0, _RT[typ], val)


def rdel(hive, path, name):
    try:
        with _open(hive, path, True) as k:
            winreg.DeleteValue(k, name)
    except OSError:
        pass


def _mk(**kw):
    kw.setdefault("admin", False)
    kw.setdefault("rec", True)       # included in "Apply recommended"
    kw.setdefault("reboot", False)
    return kw


def reg_tweak(id, cat, title, desc, items, post=None, **kw):
    """items: (hive, path, name, type 'd'/'s'/'b', target value) - or a function that returns such a list."""
    its = lambda: items() if callable(items) else items

    def check(p):
        rows = its()
        return bool(rows) and all((lambda r, v: r is not None and r[0] == v)(rget(h, pa, n), v)
                                  for h, pa, n, ty, v in rows)

    def apply(p):
        bak = p.setdefault("opt_bak", {})
        if id not in bak:   # remember the original values (only the first time)
            rows = []
            for h, pa, n, ty, v in its():
                r = rget(h, pa, n)
                rows.append([h, pa, n, r is not None, _RN.get(r[1]) if r else None,
                             (r[0].hex() if isinstance(r[0], bytes) else r[0]) if r else None])
            bak[id] = rows
        for h, pa, n, ty, v in its():
            rset(h, pa, n, ty, v)
        if post:
            try:
                post()   # live update; the registry change itself already worked
            except Exception:
                pass

    def revert(p):
        rows = p.get("opt_bak", {}).pop(id, None)
        if rows is None:   # no backup: remove our values so Windows uses its default
            for h, pa, n, ty, v in its():
                rdel(h, pa, n)
        else:
            for h, pa, n, ex, ty, v in rows:
                if ex and ty in _RT:
                    rset(h, pa, n, ty, bytes.fromhex(v) if ty == "b" else v)
                else:
                    rdel(h, pa, n)
        if post:
            try:
                post()   # live update; the registry change itself already worked
            except Exception:
                pass

    return _mk(id=id, cat=cat, title=title, desc=desc, apply=apply, revert=revert, check=check, **kw)


def svc_tweak(id, cat, title, desc, names, **kw):
    """Disables Windows services (and stops them). The original start type is restored on undo."""
    base = r"SYSTEM\CurrentControlSet\Services\%s"

    def start(n):
        r, d = rget("HKLM", base % n, "Start"), rget("HKLM", base % n, "DelayedAutostart")
        return None if r is None else [r[0], bool(d and d[0])]

    def check(p):
        st = [start(n) for n in names]
        st = [s for s in st if s]
        return bool(st) and all(s[0] == 4 for s in st)

    def apply(p):
        bak = p.setdefault("opt_bak", {})
        if id not in bak:
            bak[id] = {n: start(n) for n in names if start(n)}
        for n in bak[id]:
            run(["sc", "config", n, "start=", "disabled"])
            run(["sc", "stop", n])

    def revert(p):
        bak = p.get("opt_bak", {}).pop(id, None) or {n: [2, False] for n in names if start(n)}
        for n, (s, d) in bak.items():
            run(["sc", "config", n, "start=", {2: "delayed-auto" if d else "auto", 3: "demand"}.get(s, "auto")])

    return _mk(id=id, cat=cat, title=title, desc=desc, apply=apply, revert=revert, check=check, admin=True, **kw)


# ---- power plan
_GUID = re.compile(r"([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})", re.I)


def _active_plan():
    m = _GUID.search(run(["powercfg", "/getactivescheme"])[1])
    return m.group(1).lower() if m else None


def plan_apply(p):
    guid = p.get("plan_guid")
    if not guid or guid not in run(["powercfg", "/list"])[1].lower():
        for src in ("e9a42b02-d5df-448d-aa00-03f14749eb61", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"):
            m = _GUID.search(run(["powercfg", "-duplicatescheme", src])[1])
            if m:
                guid = p["plan_guid"] = m.group(1).lower()
                break
        else:
            raise RuntimeError("Windows would not create a performance power plan on this PC.")
    cur = _active_plan()
    if cur and cur != guid:
        p["plan_prev"] = cur
    run(["powercfg", "/setactive", guid])


def plan_revert(p):
    prev = p.pop("plan_prev", None) or "381b4222-f694-41f0-9685-ff5bb260df2e"
    if run(["powercfg", "/setactive", prev])[0] != 0:
        run(["powercfg", "/setactive", "381b4222-f694-41f0-9685-ff5bb260df2e"])


def plan_check(p):
    return bool(p.get("plan_guid")) and _active_plan() == p.get("plan_guid")


# ---- tweak specific helpers
def _mouse_post():
    """Applies the pointer-acceleration setting right away (no sign-out needed)."""
    def g(n):
        r = rget("HKCU", r"Control Panel\Mouse", n)
        try:
            return int(r[0])
        except Exception:
            return 0
    vals = (ctypes.c_int * 3)(g("MouseThreshold1"), g("MouseThreshold2"), g("MouseSpeed"))
    ctypes.windll.user32.SystemParametersInfoW(0x0004, 0, vals, 3)   # SPI_SETMOUSE


def _dx_items():
    path = r"Software\Microsoft\DirectX\UserGpuPreferences"
    r = rget("HKCU", path, "DirectXUserGlobalSettings")
    parts = [x for x in (r[0] if r and isinstance(r[0], str) else "").split(";")
             if x and not x.startswith("SwapEffectUpgradeEnable")]   # keep the user's other GPU settings
    return [("HKCU", path, "DirectXUserGlobalSettings", "s", ";".join(parts + ["SwapEffectUpgradeEnable=1"]) + ";")]


def _nagle_items():
    base, out = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces", []
    try:
        with _open("HKLM", base) as k:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                pa = base + "\\" + sub
                if rget("HKLM", pa, "DhcpIPAddress") or rget("HKLM", pa, "IPAddress"):
                    out += [("HKLM", pa, "TcpAckFrequency", "d", 1), ("HKLM", pa, "TCPNoDelay", "d", 1)]
    except OSError:
        pass
    return out


_SP = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
_CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
_GCS = r"System\GameConfigStore"
_POL = r"SOFTWARE\Policies\Microsoft\Windows"
_ACC = r"Control Panel\Accessibility"
TWEAKS = [
    # ---- gaming
    _mk(id="power", cat="game", title="Ultimate Performance power plan", desc="No CPU power saving. Best on desktops.",
        apply=plan_apply, revert=plan_revert, check=plan_check, admin=True),
    reg_tweak("gamemode", "game", "Windows Game Mode on", "Gives your game priority over background tasks.",
              [("HKCU", r"Software\Microsoft\GameBar", "AllowAutoGameMode", "d", 1),
               ("HKCU", r"Software\Microsoft\GameBar", "AutoGameModeEnabled", "d", 1)]),
    reg_tweak("dvr", "game", "Turn off Game DVR recording", "Stops background capture that costs FPS.",
              [("HKCU", _GCS, "GameDVR_Enabled", "d", 0),
               ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", "d", 0)]),
    reg_tweak("mmcss", "game", "Games get higher CPU/GPU priority", "Multimedia scheduler favors games.",
              [("HKLM", _SP, "SystemResponsiveness", "d", 0), ("HKLM", _SP + r"\Tasks\Games", "GPU Priority", "d", 8),
               ("HKLM", _SP + r"\Tasks\Games", "Priority", "d", 6),
               ("HKLM", _SP + r"\Tasks\Games", "Scheduling Category", "s", "High"),
               ("HKLM", _SP + r"\Tasks\Games", "SFIO Priority", "s", "High")], admin=True),
    reg_tweak("prio", "game", "Foreground app boost", "The window you play in gets the CPU first.",
              [("HKLM", r"SYSTEM\CurrentControlSet\Control\PriorityControl", "Win32PrioritySeparation", "d", 38)],
              admin=True),
    reg_tweak("mouse", "game", "Mouse: no pointer acceleration", "Raw 1:1 mouse movement in games and Windows.",
              [("HKCU", r"Control Panel\Mouse", "MouseSpeed", "s", "0"),
               ("HKCU", r"Control Panel\Mouse", "MouseThreshold1", "s", "0"),
               ("HKCU", r"Control Panel\Mouse", "MouseThreshold2", "s", "0")], post=_mouse_post),
    reg_tweak("sticky", "game", "No Sticky Keys popups", "Stops the Shift x5 popup from alt-tabbing you out.",
              [("HKCU", _ACC + r"\StickyKeys", "Flags", "s", "506"), ("HKCU", _ACC + r"\ToggleKeys", "Flags", "s", "58"),
               ("HKCU", _ACC + r"\Keyboard Response", "Flags", "s", "122")]),
    reg_tweak("windowed", "game", "Optimize windowed games", "Lower latency in borderless/windowed mode.", _dx_items),
    reg_tweak("hags", "game", "Hardware GPU scheduling", "Newer NVIDIA/AMD cards. Needs a restart.",
              [("HKLM", r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers", "HwSchMode", "d", 2)],
              admin=True, reboot=True, rec=False),
    reg_tweak("fso", "game", "Turn off fullscreen optimizations", "Some games run better. Test it yourself.",
              [("HKCU", _GCS, "GameDVR_FSEBehaviorMode", "d", 2), ("HKCU", _GCS, "GameDVR_FSEBehavior", "d", 2),
               ("HKCU", _GCS, "GameDVR_HonorUserFSEBehaviorMode", "d", 1),
               ("HKCU", _GCS, "GameDVR_DXGIHonorFSEWindowsCompatible", "d", 1)], rec=False),
    # ---- system
    reg_tweak("anim", "sys", "Snappier Windows (no animations)", "Turns off animations and transparency.",
              [("HKCU", r"Control Panel\Desktop\WindowMetrics", "MinAnimate", "s", "0"),
               ("HKCU", r"Control Panel\Desktop", "MenuShowDelay", "s", "0"),
               ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "TaskbarAnimations", "d", 0),
               ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "EnableTransparency", "d", 0)]),
    reg_tweak("sdelay", "sys", "No startup app delay", "Startup programs load right away.",
              [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\Serialize", "StartupDelayInMSec", "d", 0)]),
    reg_tweak("bgapps", "sys", "Stop background apps", "Store apps stop running when closed.",
              [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                "GlobalUserDisabled", "d", 1)]),
    reg_tweak("tips", "sys", "No ads and suggestions", "No tips, promoted apps or silent installs.",
              [("HKCU", _CDM, n, "d", 0) for n in ("SystemPaneSuggestionsEnabled", "SubscribedContent-338388Enabled",
                                                   "SubscribedContent-338389Enabled", "SoftLandingEnabled",
                                                   "SilentInstalledAppsEnabled", "RotatingLockScreenOverlayEnabled")]),
    reg_tweak("faststart", "sys", "Turn off Fast Startup", "A real full shutdown. Fixes odd driver bugs.",
              [("HKLM", r"SYSTEM\CurrentControlSet\Control\Session Manager\Power", "HiberbootEnabled", "d", 0)],
              admin=True, rec=False),
    reg_tweak("shutdown", "sys", "Faster shutdown", "Apps are given 2 s instead of 5 s to close.",
              [("HKLM", r"SYSTEM\CurrentControlSet\Control", "WaitToKillServiceTimeout", "s", "2000"),
               ("HKCU", r"Control Panel\Desktop", "WaitToKillAppTimeout", "s", "2000"),
               ("HKCU", r"Control Panel\Desktop", "HungAppTimeout", "s", "2000")], admin=True, rec=False),
    svc_tweak("sysmain", "sys", "Turn off SysMain (Superfetch)", "SSD only! Makes an old hard drive slower.",
              ["SysMain"], rec=False),
    # ---- network
    reg_tweak("nagle", "net", "Lower online latency (Nagle off)", "Sends game packets straight away.",
              _nagle_items, admin=True),
    reg_tweak("throttle", "net", "No network throttling", "Removes Windows' media network limit.",
              [("HKLM", _SP, "NetworkThrottlingIndex", "d", 4294967295)], admin=True),
    reg_tweak("deliv", "net", "Stop Windows Update sharing", "Your PC no longer uploads updates to others.",
              [("HKLM", _POL + r"\DeliveryOptimization", "DODownloadMode", "d", 0)], admin=True),
    # ---- privacy
    reg_tweak("telem", "priv", "Minimum telemetry", "Sends as little data to Microsoft as possible.",
              [("HKLM", _POL + r"\DataCollection", "AllowTelemetry", "d", 0),
               ("HKLM", _POL + r"\DataCollection", "DoNotShowFeedbackNotifications", "d", 1)], admin=True),
    svc_tweak("diag", "priv", "Stop the telemetry service", "Turns off DiagTrack, a background CPU/disk user.",
              ["DiagTrack", "dmwappushservice"]),
    reg_tweak("adid", "priv", "Turn off advertising ID", "Apps can't track you for ads.",
              [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", "d", 0)]),
    reg_tweak("activity", "priv", "Turn off activity history", "Windows stops logging what you open.",
              [("HKLM", _POL + r"\System", n, "d", 0) for n in ("EnableActivityFeed", "PublishUserActivities",
                                                                  "UploadUserActivities")], admin=True),
    reg_tweak("wer", "priv", "Turn off error reporting", "No crash reports sent to Microsoft.",
              [("HKLM", r"SOFTWARE\Microsoft\Windows\Windows Error Reporting", "Disabled", "d", 1)], admin=True),
]


# ---- cleanup + other one-click actions
def _clean(*paths):
    freed = 0
    for path in paths:
        if not path or not os.path.isdir(path):
            continue
        for root, dirs, files in os.walk(path, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    os.remove(fp)
                    freed += sz
                except OSError:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass
    return freed


def _freed(n):
    return f"Freed {n / 1048576:.1f} MB" if n < 1073741824 else f"Freed {n / 1073741824:.2f} GB"


def _env(*parts):
    base = os.environ.get(parts[0], "")
    return os.path.join(base, *parts[1:]) if base else ""


def act_temp(p):
    return _freed(_clean(os.environ.get("TEMP"), _env("WINDIR", "Temp")))


def act_shader(p):
    la = "LOCALAPPDATA"
    return _freed(_clean(_env(la, "D3DSCache"), _env(la, "NVIDIA", "DXCache"), _env(la, "NVIDIA", "GLCache"),
                         _env(la, "AMD", "DxCache"), _env(la, "AMD", "GLCache")))


def act_dumps(p):
    return _freed(_clean(_env("LOCALAPPDATA", "CrashDumps"), _env("LOCALAPPDATA", "Microsoft", "Windows", "WER"),
                         _env("PROGRAMDATA", "Microsoft", "Windows", "WER", "ReportQueue"),
                         _env("WINDIR", "Minidump")))


def act_recycle(p):
    ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)   # no confirmation / progress / sound
    return "Recycle Bin emptied"


def act_dns(p):
    run(["ipconfig", "/flushdns"])
    return "DNS cache flushed"


ACTIONS = [
    dict(id="temp", cat="clean", title="Temporary files", desc="Windows and app temp folders.", run=act_temp),
    dict(id="shader", cat="clean", title="Shader caches", desc="NVIDIA / AMD / DirectX. Games rebuild them once.",
         run=act_shader),
    dict(id="dumps", cat="clean", title="Crash dumps and error reports", desc="Old crash files.", run=act_dumps),
    dict(id="recycle", cat="clean", title="Empty Recycle Bin", desc="Permanently deletes what is in the bin.",
         run=act_recycle, confirm="Permanently delete everything in the Recycle Bin?"),
    dict(id="dns", cat="clean", title="Flush DNS cache", desc="Fixes sites that won't load after a network change.",
         run=act_dns),
]


def make_restore_point():
    c, o = run(["powershell", "-NoProfile", "-Command", "Checkpoint-Computer -Description 'Define Optimization' "
                "-RestorePointType MODIFY_SETTINGS -ErrorAction Stop"], 180)
    if c != 0:
        raise RuntimeError("Could not create it. System Protection must be on, and Windows allows one per 24 h.")
    return "Restore point created"


# ---- startup programs (same switch as Task Manager > Startup apps)
_RUNKEYS = [("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Run"),
            ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run", "Run"),
            ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32")]
_APPR = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved" + "\\"


def startup_list():
    out = []
    for hive, path, ap in _RUNKEYS:
        try:
            with _open(hive, path) as k:
                i = 0
                while True:
                    try:
                        name, cmd, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    r = rget(hive, _APPR + ap, name)
                    on = not (r and isinstance(r[0], bytes) and r[0] and r[0][0] & 1)
                    out.append(dict(hive=hive, ap=_APPR + ap, name=name, cmd=str(cmd), on=on))
        except OSError:
            pass
    return sorted(out, key=lambda e: e["name"].lower())


def startup_set(e, on):
    rset(e["hive"], e["ap"], e["name"], "b", (b"\x02" if on else b"\x03") + b"\x00" * 11)


def profile_tweaks(level):
    if level == "safe":
        return [t for t in TWEAKS if t["id"] in SAFE_IDS]
    if level == "bal":
        return [t for t in TWEAKS if t["rec"]]
    return [t for t in TWEAKS if t["id"] != "sysmain"]


def opt_apply(t, p):
    t["apply"](p)
    a = p.setdefault("opt_applied", [])
    if t["id"] not in a:
        a.append(t["id"])


def opt_revert(t, p):
    t["revert"](p)
    a = p.setdefault("opt_applied", [])
    if t["id"] in a:
        a.remove(t["id"])





# ---- games: Epic Games accounts (browser login, the Epic Games Launcher is not needed)
# Same sign-in the open-source Legendary and Heroic launchers use: log in once in the browser, paste the code,
# and the app keeps a refresh token. Games are then started directly with a one-time exchange code.
EPIC_CLIENT = ("34a02cf8f4414e29b15921876da36f9a", "daafbccc737745039dffe53d94fc76cf")
EPIC_UA = "UELauncher/11.0.1-14907503+++Portal+Release-Live Windows/10.0.19041.1.256.64bit"
EPIC_OAUTH = "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/"
EPIC_LOGIN = ("https://www.epicgames.com/id/login?redirectUrl=" + urllib.parse.quote(
    "https://www.epicgames.com/id/api/redirect?clientId=%s&responseType=code" % EPIC_CLIENT[0], safe=""))
AUTH_FILE = os.path.join(DIR, "epic_auth.json")   # refresh tokens, kept apart from the crosshair data


class EpicHTTP(RuntimeError):
    """Epic answered with an error (wrong code, expired login...)."""


def _epic(url, form=None, bearer=None, basic=False):
    h = {"User-Agent": EPIC_UA}
    if basic:
        h["Authorization"] = "basic " + base64.b64encode(":".join(EPIC_CLIENT).encode()).decode()
    elif bearer:
        h["Authorization"] = "bearer " + bearer
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("errorMessage")
        except Exception:
            msg = None
        raise EpicHTTP(msg or f"Epic returned error {e.code}")
    except (urllib.error.URLError, OSError):
        raise RuntimeError("Could not reach Epic. Check your internet connection.")


def auth_load():
    try:
        with open(AUTH_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def auth_save(d):
    os.makedirs(DIR, exist_ok=True)
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f)


def epic_login(text):
    """Exchanges the code from the Epic login page (the whole page text or just the code) for a session."""
    m = (re.search(r'"authorizationCode"\s*:\s*"([0-9a-fA-F]{32})"', text)
         or re.search(r"(?<![0-9a-zA-Z])([0-9a-fA-F]{32})(?![0-9a-zA-Z])", text))
    if not m:
        raise RuntimeError("That does not look like an Epic code. Copy the whole page after logging in.")
    return _epic(EPIC_OAUTH + "token", {"grant_type": "authorization_code", "code": m.group(1).lower(),
                                        "token_type": "eg1"}, basic=True)


def epic_session(name):
    """Fresh access token for a saved user. Epic hands out a new refresh token every time, so we store it."""
    a = auth_load()
    u = a.get(name)
    if not u:
        raise RuntimeError(f"No saved login for {name}. Use Add user to log in again.")
    try:
        t = _epic(EPIC_OAUTH + "token", {"grant_type": "refresh_token", "refresh_token": u["refresh_token"],
                                         "token_type": "eg1"}, basic=True)
    except EpicHTTP:
        raise RuntimeError(f"The login for {name} has expired. Use Add user (same name) to log in again.")
    a[name] = dict(account_id=t["account_id"], display_name=t.get("displayName", u.get("display_name", "")),
                   refresh_token=t["refresh_token"])
    auth_save(a)
    return t


def epic_library(tok):
    """Games this account owns: [[appName, title], ...]."""
    bearer = tok["access_token"]
    assets = _epic("https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/public/assets/Windows"
                   "?label=Live", bearer=bearer)
    items, seen = [], set()
    for a in assets:
        ns, item, app = a.get("namespace"), a.get("catalogItemId"), a.get("appName")
        if ns and item and app and ns != "ue" and app not in seen:
            seen.add(app)
            items.append((app, ns, item))

    def meta(x):
        app, ns, item = x
        try:
            d = _epic(f"https://catalog-public-service-prod06.ol.epicgames.com/catalog/api/shared/namespace/{ns}"
                      f"/bulk/items?id={item}&includeDLCDetails=true&includeMainGameDetails=true&country=US"
                      "&locale=en", bearer=bearer)
            return d.get(item) or {}
        except RuntimeError:
            return {}

    with ThreadPoolExecutor(max_workers=8) as ex:
        metas = list(ex.map(meta, items))
    out = []
    for (app, ns, item), m in zip(items, metas):
        if m.get("mainGameItem"):   # DLC
            continue
        if m and not ({c.get("path") for c in m.get("categories", [])} & {"games", "applications"}):
            continue
        out.append([app, m.get("title") or app])
    return sorted(out, key=lambda g: g[1].lower())


def scan_installed(info=None):
    """Games installed through the Epic Games Launcher: {appName in lower case: manifest}.
    `info` (a dict) is filled with the folder, how many manifests were read and why some games were skipped."""
    info = info if info is not None else {}
    d = _env("PROGRAMDATA", "Epic", "EpicGamesLauncher", "Data", "Manifests")
    out = {}
    info.update(dir=d, files=0, unreadable=0, skipped={}, error="")
    if not d or not os.path.isdir(d):
        info["error"] = "Epic's manifest folder was not found"
        return out
    try:
        names = os.listdir(d)
    except OSError as e:
        info["error"] = f"Could not read Epic's manifest folder ({e.__class__.__name__})"
        return out
    for fn in names:
        if not fn.lower().endswith(".item"):
            continue
        info["files"] += 1
        try:
            with open(os.path.join(d, fn), encoding="utf-8-sig") as f:
                m = json.load(f)
        except Exception:
            info["unreadable"] += 1
            continue
        app, loc, exe = m.get("AppName"), m.get("InstallLocation"), m.get("LaunchExecutable")
        if not app or not exe:   # DLC and add-ons have no executable
            continue
        key = app.lower()
        if m.get("bIsIncompleteInstall"):
            why = "installation not finished"
        elif not loc or not os.path.isdir(loc):
            why = "install folder missing"
        elif not os.path.exists(os.path.join(loc, exe)):
            why = "game file missing"
        else:
            out[key] = m
            continue
        info["skipped"][key] = why
    return out


def launch_game(name, app, installed):
    """Logs in as `name` and starts the game directly, no Epic Games Launcher involved."""
    m = installed.get(app.lower())
    if not m:
        raise RuntimeError("Not installed. Install it with the Epic Games Launcher first.")
    tok = epic_session(name)
    code = _epic(EPIC_OAUTH + "exchange", bearer=tok["access_token"])["code"]
    loc = m["InstallLocation"]
    cmd = [os.path.join(loc, m["LaunchExecutable"])] + (m.get("LaunchCommand") or "").split() + [
        "-AUTH_LOGIN=unused", "-AUTH_PASSWORD=" + code, "-AUTH_TYPE=exchangecode", "-epicapp=" + app,
        "-epicenv=Prod", "-EpicPortal", "-epicusername=" + str(tok.get("displayName", "")),
        "-epicuserid=" + tok["account_id"], "-epiclocale=en-US"]
    if m.get("CatalogNamespace"):
        cmd.append("-epicsandboxid=" + m["CatalogNamespace"])
    subprocess.Popen(cmd, cwd=loc, close_fds=True)


# ---- system information for the dashboard
class _MEM(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def sysinfo():
    d = dict(os="Windows", ver="", edition="", cpu="Unknown", gpu="Unknown", threads=os.cpu_count() or 0,
             ram_total=0.0, ram_used=0.0, disks=[])
    try:
        if winreg:
            cvk = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"

            def g(n):
                r = rget("HKLM", cvk, n)
                return str(r[0]) if r else ""
            build, name = g("CurrentBuild"), g("ProductName")
            if build.isdigit() and int(build) >= 22000:
                name = name.replace("Windows 10", "Windows 11")
            d["os"] = name or "Windows"
            d["ver"] = " · ".join(x for x in (g("DisplayVersion") or g("ReleaseId"), ("build " + build) if build else "") if x)
            d["edition"] = g("EditionID")
            r = rget("HKLM", r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString")
            if r:
                d["cpu"] = " ".join(str(r[0]).split())
            base, gpus = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11cf-bfc1-08002be10318}", []
            for i in range(10):
                r = rget("HKLM", "%s\\%04d" % (base, i), "DriverDesc")
                if r and "basic" not in str(r[0]).lower() and str(r[0]) not in gpus:
                    gpus.append(str(r[0]))
            if gpus:
                pref = [x for x in gpus if re.search(r"nvidia|geforce|radeon|arc ", x, re.I)]
                d["gpu"] = (pref or gpus)[0]
    except Exception:
        pass
    try:
        m = _MEM()
        m.dwLength = ctypes.sizeof(_MEM)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        d["ram_total"] = m.ullTotalPhys / 1073741824
        d["ram_used"] = (m.ullTotalPhys - m.ullAvailPhys) / 1073741824
    except Exception:
        pass
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, ch in enumerate(string.ascii_uppercase):
            if mask >> i & 1 and ctypes.windll.kernel32.GetDriveTypeW(ch + ":\\") == 3:   # fixed drives only
                u = shutil.disk_usage(ch + ":\\")
                d["disks"].append((ch + ":", u.total / 1073741824, u.free / 1073741824))
    except Exception:
        pass
    return d


RISK = {"gamemode": "safe", "dvr": "safe", "mouse": "safe", "sticky": "safe", "windowed": "safe", "anim": "safe",
        "sdelay": "safe", "bgapps": "safe", "tips": "safe", "adid": "safe", "deliv": "safe",
        "sysmain": "risky", "hags": "risky"}
RISK_LABEL = {"safe": "Safe", "moderate": "Moderate", "risky": "Risky"}
RISK_COL = {"safe": GOOD, "moderate": WARN, "risky": BAD}
for _t in TWEAKS:
    _t["risk"] = RISK.get(_t["id"], "moderate")


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(NAME)
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        center_window(self.root, WIN_W, WIN_H)
        self.s, self.saved, self.prefs = load()
        self.tab, self.xsub, self.sub, self.pvbg = "dash", "look", "inner", "#0a0c10"
        self.tool, self.mx, self.my = "draw", False, False
        self.sel, self.lib_off, self.cellid = None, 0, {}
        self.ov, self.show_ov, self.f8_down = None, True, False
        self.opt_cat, self.opt_off, self.opt_state, self.opt_start = "game", 0, {}, []
        self.opt_msg, self.opt_busy, self.opt_res = "", False, {}
        self.adm = is_admin()
        self.g_off, self.g_mode, self.installed = 0, "mine", set()
        self.g_refresh()
        self.init_display()
        self.opt_refresh()
        self.info = sysinfo()

        self.c = tk.Canvas(self.root, width=WIN_W, height=WIN_H, bg=BG, highlightthickness=0)
        self.c.pack()
        dark_title(self.root)
        self.sf = Surface(self.c)
        self.c.bind("<Button-3>", lambda e: self.paint_at(e.x, e.y, True))
        self.c.bind("<B3-Motion>", lambda e: self.paint_at(e.x, e.y, True))
        self.vw, self.vh = tk.StringVar(value=str(self.prefs["last_w"])), tk.StringVar(value=str(self.prefs["last_h"]))
        self.hz = 0
        ekw = dict(font=(FAM, -14), bg=INPUT, fg=TEXT, insertbackground=TEXT, relief="flat", justify="center",
                   highlightthickness=0, bd=0)
        self.ew = tk.Entry(self.root, textvariable=self.vw, **ekw)
        self.eh = tk.Entry(self.root, textvariable=self.vh, **ekw)

        self.make_overlay()
        self.render()
        self.draw_overlay()
        self.tick()
        self.poll_hotkey()
        if getattr(sys, "frozen", False):
            self.root.after(3000, self.check_updates)  # silent check at startup
        self.root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---------- display state ----------
    def init_display(self):
        ss = screen_size() or (self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.cur, self.native, self.modes, self.presets = (ss[0], ss[1], 0), (ss[0], ss[1], 0), [], []
        self.last_ss = ss
        if not DISPLAY_OK:
            return
        try:
            self.cur = current_mode()
            self.modes = list_modes()
            try:
                self.native = registry_mode()
            except Exception:
                self.native = self.cur
            self.presets = self.find_presets()
        except Exception:
            pass

    def find_presets(self):
        out, (nw, nh, _) = [], self.native
        for w, h in CANDIDATES:
            if (w, h) == (nw, nh) or w > nw or h > nh:
                continue
            if any(m[0] == w and m[1] == h for m in self.modes) or set_mode(w, h, self.cur[2], test=True) == 0:
                out.append((w, h))
        out.sort(key=lambda r: -r[0] * r[1])
        return out[:8]

    def rates_for(self, w, h):
        return sorted({m[2] for m in self.modes if m[0] == w and m[1] == h}, reverse=True)

    def after_res_change(self):
        try:
            self.cur = current_mode()
        except Exception:
            ss = screen_size()
            if ss:
                self.cur = (ss[0], ss[1], self.cur[2])
        self.last_ss = (self.cur[0], self.cur[1])
        self.place_overlay()
        self.render()
        self.draw_overlay()

    def apply_stretch(self):
        if not DISPLAY_OK:
            return
        try:
            w, h = int(self.vw.get()), int(self.vh.get())
            assert 320 <= w <= 16384 and 240 <= h <= 16384
        except Exception:
            messagebox.showerror(NAME, "Enter the width and height as whole numbers, e.g. 1280 and 960.", parent=self.root)
            return
        rates = self.rates_for(w, h)
        hz = self.hz if self.hz in rates else (self.cur[2] if self.cur[2] in rates or not rates else rates[0])
        prev = self.cur
        if set_mode(w, h, hz, test=True) != 0:
            messagebox.showerror(NAME, f"Your display or driver does not offer {w}x{h}.\nPick one of the presets "
                                       "or try another size.", parent=self.root)
            return
        code = set_mode(w, h, hz)
        if code != 0:
            messagebox.showerror(NAME, f"Windows could not switch to {w}x{h} (code {code}).", parent=self.root)
            return
        self.prefs.update(last_w=w, last_h=h)
        self.after_res_change()
        d = KeepDialog(self.root, f"{w}x{h}", f"{prev[0]}x{prev[1]}")
        self.root.wait_window(d)
        if not d.keep:
            set_mode(prev[0], prev[1], prev[2])
            self.after_res_change()
        else:
            save(self.s, self.saved, self.prefs)

    def go_native(self):
        if not DISPLAY_OK:
            return
        try:
            if set_mode(*self.native) != 0:
                reset_mode()
        except Exception:
            pass
        self.after_res_change()

    def pick_res(self, w, h):
        self.vw.set(str(w))
        self.vh.set(str(h))
        self.hz = 0
        self.render()

    def cycle_hz(self):
        try:
            rates = self.rates_for(int(self.vw.get()), int(self.vh.get()))
        except ValueError:
            return
        if rates:
            opts = [0] + rates
            self.hz = opts[(opts.index(self.hz) + 1) % len(opts)] if self.hz in opts else 0
            self.render()

    # ---------- render ----------
    def render(self):
        cv = self.c
        cv.delete("ui")
        self.sf.clear()
        self.cellid = {}
        cv.create_rectangle(0, 0, WIN_W, WIN_H, fill=BG, outline="", tags="ui")
        self.draw_sidebar()
        self.draw_header()
        keep, n0 = set(cv.find_withtag("ui")), len(self.sf.items)
        side_xh = self.tab in ("xh", "stretch")
        if side_xh:
            self.draw_left()
        else:
            cv.delete("pv")   # crosshair preview belongs to the crosshair pages
        getattr(self, "page_" + self.tab)()
        for item in cv.find_withtag("ui"):   # move the page (and its click areas) into place
            if item not in keep:
                cv.move(item, OX, -DY)
        for it in self.sf.items[n0:]:
            x0, y0, x1, y1 = it["box"]
            it["box"] = (x0 + OX, y0 - DY, x1 + OX, y1 - DY)
        if (self.tab, self.xsub) == ("xh", "draw"):
            self.grid_org = (self.grid_org[0] + OX, self.grid_org[1] - DY)
        if side_xh:
            self.draw_preview()

    def draw_sidebar(self):
        cv, sf = self.c, self.sf
        cv.create_rectangle(0, 0, SB_W, WIN_H, fill=SIDE, outline="", tags="ui")
        cv.create_line(SB_W, 0, SB_W, WIN_H, fill=STROKE, tags="ui")
        rrect(cv, 20, 22, 56, 58, 10, ACCENT)
        icon(cv, "crosshair", 38, 40, ON_ACCENT)
        text(cv, 68, 33, NAME, TEXT, F_H)
        text(cv, 68, 51, "v" + VERSION, DIM, F_XS)
        y = 92
        for group, items in NAV:
            text(cv, 24, y, group, DIM, F_XS)
            y += 18
            for key, label, ic in items:
                on = self.tab == key
                if on:
                    rrect(cv, 12, y, SB_W - 12, y + 40, 6, CARD)
                    rrect(cv, 12, y + 11, 15, y + 29, 1.5, ACCENT)
                icon(cv, ic, 40, y + 20, ACCENT if on else MUTED)
                text(cv, 64, y + 20, label, TEXT if on else MUTED, F_B if on else F_M)
                sf.add((12, y, SB_W - 12, y + 40), click=lambda px, py, k=key: self.show(k))
                y += 44
            y += 14
        # permission card at the bottom
        top = WIN_H - 120
        self.card(12, top, SB_W - 12, WIN_H - 16)
        cv.create_oval(28, top + 19, 36, top + 27, fill=GOOD if self.adm else WARN, outline="", tags="ui")
        text(cv, 44, top + 23, "Administrator" if self.adm else "Standard user", TEXT, F_B)
        if self.adm:
            text(cv, 28, top + 52, "All tweaks are available.", MUTED, F_XS)
            text(cv, 28, top + 70, "Changes are saved so they", DIM, F_XS)
            text(cv, 28, top + 84, "can be undone.", DIM, F_XS)
        else:
            text(cv, 28, top + 46, "Some tweaks need admin.", MUTED, F_XS)
            btn(cv, sf, 24, top + 62, SB_W - 24, top + 92, "Run as administrator", self.opt_admin, "pri", font=F_S,
                ic="shield")

    def draw_header(self):
        cv, sf = self.c, self.sf
        title, sub = HEAD[self.tab]
        text(cv, SB_W + 24, 46, title, TEXT, F_L)
        text(cv, SB_W + 24, 80, sub, MUTED, F_S)
        lab = "Hide crosshair" if self.show_ov else "Show crosshair"
        w = max(tw("Hide crosshair", F_B), tw("Show crosshair", F_B)) + 40
        x1 = WIN_W - 28
        btn(cv, sf, x1 - w, 30, x1, 66, lab, self.toggle_ov, "pri" if self.show_ov else "sec")
        rrect(cv, x1 - w - 46, 30, x1 - w - 10, 66, 6, CARD2, outline=STROKE)
        icon(cv, "refresh", x1 - w - 28, 48, TEXT)
        sf.add((x1 - w - 46, 30, x1 - w - 10, 66), click=lambda x, y: self.check_updates(True))
        text(cv, x1, 80, "F8 = on/off", DIM, F_XS, "e")

    # ---------- shared pieces ----------
    def card(self, x0, y0, x1, y1, fill=CARD, r=8):
        rrect(self.c, x0, y0, x1, y1, r, fill, outline=STROKE)

    def tab_item(self, x, y, w, label, on, fn):
        """Pivot tab: text with an accent underline when selected."""
        text(self.c, x + w / 2, y + 16, label, TEXT if on else MUTED, F_B, "center")
        if on:
            rrect(self.c, x + 10, y + 32, x + w - 10, y + 35, 1.5, ACCENT)
        self.sf.add((x, y, x + w, y + 36), click=lambda px, py: fn())

    def draw_preview(self):
        draw(self.c, 225 + OX, 278 - DY, self.s, "pv")
        self.c.tag_raise("pv")

    def srow(self, x, y, x1, label, key, lo, hi):
        text(self.c, x, y, label, TEXT, F_M)
        slider(self.c, self.sf, x + 196, y, x1 - x - 196 - 66, self.s[key], lo, hi, lambda v, k=key: self.set(k, v))
        rrect(self.c, x1 - 52, y - 13, x1, y + 13, 6, INPUT, outline=STROKE)
        text(self.c, x1 - 26, y, str(self.s[key]), TEXT, F_B, "center")

    def tog(self, x, y, label, key):
        return toggle(self.c, self.sf, x, y, label, bool(self.s[key]), lambda k=key: self.set(k, not self.s[k]))

    def crow(self, x, y, x1, label, key):
        text(self.c, x, y, label, TEXT, F_M)
        sx = x + 196
        rrect(self.c, sx, y - 14, sx + 52, y + 14, 6, self.s[key], outline=STROKE)
        self.sf.add((sx, y - 14, sx + 52, y + 14), click=lambda px, py, k=key: self.pick_color(k))
        w = tw("Color wheel", F_B) + 30
        btn(self.c, self.sf, sx + 64, y - 14, sx + 64 + w, y + 14, "Color wheel", lambda k=key: self.pick_color(k))
        text(self.c, sx + 64 + w + 12, y, self.s[key].upper(), MUTED, F_B)

    def bar(self, y0, y1, hint):
        """Bottom bar with a status message on the left. Buttons are added by the caller."""
        self.card(100, y0, 972, y1)
        msg = self.opt_msg
        text(self.c, 122, (y0 + y1) / 2, fit(msg or hint, F_S, 500), TEXT if msg else MUTED, F_S)

    def draw_rows(self, rows, Y0, vis, X0=100, X1=972, RH=56):
        """Scrollable list of setting cards: tweaks (switch), startup programs (switch) or actions (Run button)."""
        cv, sf, adm = self.c, self.sf, self.adm
        n = len(rows)
        self.opt_off = max(0, min(self.opt_off, max(0, n - vis)))
        sf.add((X0, Y0, X1 + 14, Y0 + vis * RH), wheel=self.opt_scroll, cursor="")
        if not rows:
            text(cv, X0 + 4, Y0 + 14, "Nothing found here.", MUTED, F_M)
        for i in range(vis):
            idx = self.opt_off + i
            if idx >= n:
                break
            r, y = rows[idx], Y0 + i * RH
            rrect(cv, X0, y, X1, y + 50, 8, CARD, outline=STROKE)
            tags, fn, on = [], None, False
            if r["kind"] == "tw":
                t = r["t"]
                on, title, desc = bool(self.opt_state.get(t["id"])), t["title"], t["desc"]
                tags.append((RISK_LABEL[t["risk"]], RISK_COL[t["risk"]]))
                if t["admin"] and not adm:
                    tags.append(("Admin", ACCENT))
                if t["reboot"]:
                    tags.append(("Restart", MUTED))
                fn = lambda t=t: self.opt_toggle(t)
            elif r["kind"] == "st":
                e = r["e"]
                on, title, desc = e["on"], e["name"], e["cmd"]
                if e["hive"] == "HKLM" and not adm:
                    tags.append(("Admin", ACCENT))
                fn = lambda e=e: self.opt_start_toggle(e)
            else:
                a = r["a"]
                title, desc = a["title"], self.opt_res.get(a["id"]) or a["desc"]
            text(cv, X0 + 20, y + 19, fit(title, F_B, 340), TEXT, F_B)
            text(cv, X0 + 20, y + 37, fit(desc, F_XS, 460), MUTED, F_XS)
            if fn:
                sf.add((X0, y, X1, y + 50), click=lambda px, py, f=fn: f(), wheel=self.opt_scroll)
                switch(cv, sf, X1 - 62, y + 15, on, fn)
                tx = X1 - 78
            else:
                btn(cv, sf, X1 - 96, y + 10, X1 - 16, y + 40, "Run", lambda a=a: self.opt_act(a), "pri", font=F_M)
                tx = X1 - 112
            for label, col in tags:
                w = tw(label, F_XS) + 18
                rrect(cv, tx - w, y + 15, tx, y + 35, 10, "", outline=col)
                text(cv, tx - w / 2, y + 25, label, col, F_XS, "center")
                tx -= w + 6
        if n > vis:   # scroll bar
            h = vis * RH - 6
            th = max(30, h * vis / n)
            ty = Y0 + (h - th) * self.opt_off / (n - vis)
            rrect(cv, X1 + 8, Y0, X1 + 11, Y0 + h, 1.5, TRACK)
            rrect(cv, X1 + 8, ty, X1 + 11, ty + th, 1.5, MUTED)

    # ---------- dashboard ----------
    def tile(self, x0, x1, label, big, sub, frac=None):
        cv = self.c
        self.card(x0, 156, x1, 266)
        text(cv, x0 + 20, 178, label, MUTED, F_S)
        text(cv, x0 + 20, 210, big, TEXT, F_BIG)
        if frac is not None:
            rrect(cv, x0 + 20, 232, x1 - 20, 238, 3, TRACK)
            rrect(cv, x0 + 20, 232, x0 + 20 + max(6, (x1 - x0 - 40) * min(frac, 1)), 238, 3, ACCENT)
        text(cv, x0 + 20, 252, fit(sub, F_XS, x1 - x0 - 40), MUTED, F_XS)

    def page_dash(self):
        cv, sf, i = self.c, self.sf, self.info
        n_on = sum(1 for t in TWEAKS if self.opt_state.get(t["id"]))
        self.tile(100, 382, "Optimizations", f"{n_on}/{len(TWEAKS)}", "tweaks active", n_on / max(len(TWEAKS), 1))
        rt, ru = i["ram_total"], i["ram_used"]
        self.tile(395, 677, "Memory", f"{round(100 * ru / rt)}%" if rt else "n/a",
                  f"{ru:.1f} of {rt:.1f} GB in use" if rt else "Unknown", ru / rt if rt else 0)
        cw, ch, hz = self.cur
        nw, nh, _ = self.native
        self.tile(690, 972, "Display", f"{cw}×{ch}",
                  (f"{hz} Hz  ·  " if hz else "") + (f"stretched from {nw}×{nh}" if (cw, ch) != (nw, nh) else "native"))
        # system details
        self.card(100, 278, 530, 668)
        text(cv, 122, 298, "System", MUTED, F_S)
        rows = [("Operating system", i["os"]), ("Version", i["ver"] or "-"), ("Edition", i["edition"] or "-"),
                ("Processor", i["cpu"]), ("Graphics", i["gpu"]),
                ("Memory", f"{rt:.0f} GB" if rt else "-"), ("Threads", str(i["threads"] or "-"))]
        for k, (lab, val) in enumerate(rows):
            y = 328 + k * 46
            if k:
                cv.create_line(122, y - 18, 508, y - 18, fill=STROKE, tags="ui")
            text(cv, 122, y, lab, MUTED, F_S)
            text(cv, 508, y, fit(val, F_B, 270), TEXT, F_B, "e")
        # storage
        self.card(542, 278, 972, 470)
        text(cv, 564, 298, "Storage", MUTED, F_S)
        if not i["disks"]:
            text(cv, 564, 330, "No drives found.", MUTED, F_M)
        for k, (name, total, free) in enumerate(i["disks"][:4]):
            y = 328 + k * 34
            text(cv, 564, y, name, TEXT, F_B)
            text(cv, 950, y, f"{free:.0f} GB free of {total:.0f} GB", MUTED, F_XS, "e")
            used = (total - free) / total if total else 0
            rrect(cv, 564, y + 12, 950, y + 17, 2.5, TRACK)
            rrect(cv, 564, y + 12, 564 + max(5, 386 * used), y + 17, 2.5, BAD if used > 0.9 else ACCENT)
        # quick actions
        self.card(542, 482, 972, 668)
        text(cv, 564, 500, "Quick actions", MUTED, F_S)
        if self.opt_msg:
            text(cv, 950, 500, fit(self.opt_msg, F_XS, 230), TEXT, F_XS, "e")
        tmp = next(a for a in ACTIONS if a["id"] == "temp")
        W2 = 192
        for k, (lab, fn, kind) in enumerate((
                ("Apply profile", self.opt_all, "pri"), ("Restore point", self.opt_restore, "sec"),
                ("Clean temp files", lambda: self.opt_act(tmp), "sec"), ("Undo everything", self.opt_undo_all, "sec"),
                ("Check for updates", lambda: self.check_updates(True), "sec"),
                ("Run as admin" if not self.adm else "Admin active", self.opt_admin if not self.adm else (lambda: None),
                 "sec"))):
            x0, y0 = 558 + (k % 2) * (W2 + 8), 520 + (k // 2) * 46
            btn(cv, sf, x0, y0, x0 + W2, y0 + 36, lab, fn, kind, font=F_M)

    # ---------- optimize / startup / cleanup ----------
    def page_opt(self):
        cv, sf = self.c, self.sf
        if not WIN:
            self.card(100, 156, 972, 668)
            text(cv, 124, 192, "The PC optimizer only works on Windows.", TEXT, F_H)
            return
        x = 100
        for key, label in OPT_CATS:
            w = tw(label, F_B) + 36
            self.tab_item(x, 154, w, label, self.opt_cat == key, lambda k=key: self.opt_setcat(k))
            x += w + 4
        cur = self.prefs.get("opt_prof", "bal")
        x0 = 972 - 3 * 84
        text(cv, x0 - 12, 172, "Profile", MUTED, F_S, "e")
        for k, (key, label, desc) in enumerate(OPT_PROFILES):
            btn(cv, sf, x0 + k * 84, 156, x0 + k * 84 + 80, 188, label, lambda key=key: self.set_pref("opt_prof", key),
                "pri" if cur == key else "sec", font=F_M)
        rows = [dict(kind="tw", t=t) for t in TWEAKS if t["cat"] == self.opt_cat]
        self.draw_rows(rows, 204, 7)
        desc = next(d for k, _, d in OPT_PROFILES if k == cur)
        self.bar(610, 664, desc)
        btn(cv, sf, 972 - 124, 620, 972 - 14, 654, "Undo all", self.opt_undo_all, "sec")
        btn(cv, sf, 972 - 124 - 8 - 140, 620, 972 - 138, 654, "Apply profile", self.opt_all, "pri")

    def page_start(self):
        rows = [dict(kind="st", e=e) for e in self.opt_start]
        self.draw_rows(rows, 156, 8)
        self.bar(610, 664, f"{len(rows)} programs start with Windows. Changes use the same switch as Task Manager.")

    def page_clean(self):
        rows = [dict(kind="act", a=a) for a in ACTIONS]
        self.draw_rows(rows, 156, 8)
        self.bar(610, 664, "Cleanup only removes temporary files, never your documents.")
        btn(self.c, self.sf, 972 - 134, 620, 972 - 14, 654, "Clean all", self.opt_act_all, "pri")

    # ---------- crosshair pages ----------
    def draw_left(self):
        cv, sf = self.c, self.sf
        self.card(100, 156, 350, 424)
        rrect(cv, 110, 166, 340, 390, 6, self.pvbg)
        for i, col in enumerate(("#0a0c10", "#2b3a2f", "#6b7280", "#d9d9d9")):
            cx = 225 + (i - 1.5) * 34
            on = self.pvbg == col
            cv.create_oval(cx - 9, 398, cx + 9, 416, fill=col, outline=ACCENT if on else STROKE, width=2, tags="ui")
            sf.add((cx - 11, 396, cx + 11, 420), click=lambda x, y, c=col: self.set_pvbg(c))
        self.card(100, 434, 350, 668)
        text(cv, 120, 456, "Quick presets", MUTED, F_S)
        for n, (name, p) in enumerate(PRESETS.items()):
            x0, y0 = 112 + (n % 2) * 118, 476 + (n // 2) * 48
            btn(cv, sf, x0, y0, x0 + 110, y0 + 40, name, lambda p=p: self.preset(p), font=F_M)
        text(cv, 120, 640, "Tip: F8 hides or shows the crosshair.", DIM, F_XS)

    def page_xh(self):
        """One tab for everything about the crosshair, with its own sub-menu."""
        x = 364
        for key, label in XTABS:
            w = tw(label, F_B) + 36
            self.tab_item(x, 154, w, label, self.xsub == key, lambda k=key: self.xshow(k))
            x += w + 4
        getattr(self, "page_" + self.xsub)()

    def page_look(self):
        cv, sf, s = self.c, self.sf, self.s
        X0, X1 = 364, 972
        self.card(X0, 202, X1, 276)
        text(cv, X0 + 22, 218, "Style", MUTED, F_S)
        x = X0 + 20
        for name, key in STYLES:
            w = tw(name, F_B) + 30
            btn(cv, sf, x, 232, x + w, 264, name, lambda k=key: self.choose_style(k), "pri" if s["style"] == key else "sec")
            x += w + 6
        self.card(X0, 284, X1, 358)
        text(cv, X0 + 22, 300, "Color", MUTED, F_S)
        for i, col in enumerate(SWATCH):
            cx = X0 + 34 + i * 38
            on = s["color"] == col
            cv.create_oval(cx - 14, 318, cx + 14, 346, fill=col, outline=TEXT if on else STROKE,
                           width=3 if on else 1, tags="ui")
            sf.add((cx - 15, 317, cx + 15, 347), click=lambda px, py, c=col: self.set("color", c))
        bx = X0 + 34 + 8 * 38 + 6
        w = tw("Color wheel", F_B) + 34
        btn(cv, sf, bx, 316, bx + w, 348, "Color wheel", self.pick_color, "pri")
        rrect(cv, bx + w + 8, 316, X1 - 18, 348, 6, INPUT, outline=STROKE)
        text(cv, (bx + w + 8 + X1 - 18) / 2, 332, s["color"].upper(), TEXT, F_B, "center")
        self.card(X0, 366, X1, 668)
        text(cv, X0 + 22, 384, "Shape", MUTED, F_S)
        rows = (("Size", "size", 1, 60), ("Thickness", "thickness", 1, 10), ("Gap (hole in the middle)", "gap", 0, 40),
                ("Radius (circle)", "radius", 3, 80), ("Dot size", "dot_size", 1, 10))
        for i, (label, key, lo, hi) in enumerate(rows):
            self.srow(X0 + 22, 418 + i * 36, X1 - 22, label, key, lo, hi)
        x = X0 + 22
        x += self.tog(x, 594, "Center dot", "dot") + 24
        self.tog(x, 594, "Outline", "outline")
        w = tw("Open full customization", F_B) + 60
        btn(cv, sf, X0 + 22, 626, X0 + 22 + w, 658, "Open full customization", lambda: self.choose_style("advanced"),
            "pri", ic="arrow")

    def page_custom(self):
        cv, sf = self.c, self.sf
        X0, X1 = 364, 972
        x = X0
        for key, label in SUBS:
            w = tw(label, F_M) + 26
            btn(cv, sf, x, 202, x + w, 232, label, lambda k=key: self.subshow(k), "pri" if self.sub == key else "sec",
                font=F_M)
            x += w + 6
        w = tw("Same color for all", F_M) + 26
        btn(cv, sf, X1 - w, 202, X1, 232, "Same color for all", self.color_all, font=F_M)
        self.card(X0, 244, X1, 668)
        getattr(self, "sub_" + self.sub)(X0 + 22, X1 - 22)

    def sub_inner(self, x, x1):
        self.sub_lines("inner", x, x1)

    def sub_outer(self, x, x1):
        self.sub_lines("outer", x, x1)

    def sub_lines(self, g, x, x1):
        y = 264
        self.tog(x, y, "Show lines", g + "_on")
        y += 50
        self.crow(x, y, x1, "Color", g + "_color")
        y += 42
        self.srow(x, y, x1, "Length (horizontal)", g + "_len", 0, 50)
        y += 40
        self.srow(x, y, x1, "Length (vertical)", g + "_lenv", 0, 50)
        y += 36
        self.tog(x, y, "Link horizontal + vertical length", g + "_link")
        y += 42
        self.srow(x, y, x1, "Thickness", g + "_thick", 1, 10)
        y += 40
        self.srow(x, y, x1, "Offset (gap from center)", g + "_off", 0, 60)
        y += 40
        self.srow(x, y, x1, "Rotation (degrees)", g + "_rot", 0, 90)
        y += 40
        text(self.c, x, y + 12, "Show sides", TEXT, F_M)
        px = x + 130
        for side, label in (("top", "Top"), ("bottom", "Bottom"), ("left", "Left"), ("right", "Right")):
            px += self.tog(px, y, label, g + "_" + side) + 18

    def sub_cdot(self, x, x1):
        self.tog(x, 264, "Show center dot", "cdot_on")
        self.crow(x, 314, x1, "Color", "cdot_color")
        self.srow(x, 356, x1, "Size (radius)", "cdot_size", 1, 15)
        self.tog(x, 392, "Round (turn off for a square dot)", "cdot_round")

    def sub_ring(self, x, x1):
        self.tog(x, 264, "Show ring", "ring_on")
        self.crow(x, 314, x1, "Color", "ring_color")
        self.srow(x, 356, x1, "Radius", "ring_radius", 3, 80)
        self.srow(x, 396, x1, "Thickness", "ring_thick", 1, 10)

    def sub_outl(self, x, x1):
        self.tog(x, 264, "Show outline", "outline")
        self.crow(x, 314, x1, "Outline color", "outline_color")
        self.srow(x, 356, x1, "Outline thickness", "outline_thick", 1, 5)
        text(self.c, x, 400, "The outline is drawn around every part of the crosshair, in all styles.", MUTED, F_S)

    def page_draw(self):
        cv, sf, s = self.c, self.sf, self.s
        X0, X1 = 364, 972
        self.card(X0, 202, X1, 668)
        gx, gy = X0 + 20, 224
        rrect(cv, gx - 6, gy - 6, gx + N * CELL + 6, gy + N * CELL + 6, 8, INPUT)
        for i in range(N):
            for j in range(N):
                col = s["pixels"].get(f"{i},{j}")
                self.cellid[(i, j)] = cv.create_rectangle(
                    gx + i * CELL, gy + j * CELL, gx + (i + 1) * CELL, gy + (j + 1) * CELL,
                    fill=col or INPUT, outline=ACCENT if (i, j) == (N // 2, N // 2) else "#34343a", tags="ui")
        self.grid_org = (gx, gy)
        sf.add((gx, gy, gx + N * CELL, gy + N * CELL), click=lambda px, py: self.paint_at(px, py),
               drag=lambda px, py: self.paint_at(px, py), cursor="crosshair")
        text(cv, gx, gy + N * CELL + 22, "Left click = draw   ·   Right click = erase   ·   Blue square = aim point",
             MUTED, F_XS)
        tx = gx + N * CELL + 28
        x = tx
        for label, val in (("Draw", "draw"), ("Erase", "erase")):
            w = tw(label, F_B) + 34
            btn(cv, sf, x, 224, x + w, 258, label, lambda v=val: self.set_tool(v), "pri" if self.tool == val else "sec")
            x += w + 6
        toggle(cv, sf, tx, 276, "Mirror left/right", self.mx, lambda: self.set_flag("mx"))
        toggle(cv, sf, tx, 306, "Mirror up/down", self.my, lambda: self.set_flag("my"))
        text(cv, tx, 348, "Color", MUTED, F_S)
        for i, col in enumerate(SWATCH):
            cx, cy = tx + 14 + (i % 4) * 34, 374 + (i // 4) * 34
            on = s["color"] == col
            cv.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, fill=col, outline=TEXT if on else STROKE,
                           width=3 if on else 1, tags="ui")
            sf.add((cx - 13, cy - 13, cx + 13, cy + 13), click=lambda px, py, c=col: self.set("color", c))
        w = tw("Color wheel", F_B) + 34
        btn(cv, sf, tx, 446, tx + w, 478, "Color wheel", self.pick_color, "pri")
        text(cv, tx + w + 10, 462, s["color"].upper(), MUTED, F_B)
        self.srow_small(tx, 508, "Pixel size", "scale", 1, 8)
        btn(cv, sf, tx, 552, tx + 100, 584, "Clear all", self.clear_pixels)

    def srow_small(self, x, y, label, key, lo, hi):
        text(self.c, x, y - 14, label, MUTED, F_S)
        w = 150
        slider(self.c, self.sf, x + 6, y + 10, w, self.s[key], lo, hi, lambda v, k=key: self.set(k, v))
        text(self.c, x + w + 24, y + 10, str(self.s[key]), TEXT, F_B)

    def page_stretch(self):
        cv, sf = self.c, self.sf
        LX0, LX1, RX0, RX1 = 364, 660, 674, 972
        cw, ch, hz = self.cur
        nw, nh, _ = self.native
        stretched = (cw, ch) != (nw, nh)
        SUB = "#8fb6c9"
        # current display
        self.card(LX0, 156, LX1, 290, HERO)
        text(cv, LX0 + 22, 176, "Current display", SUB, F_S)
        text(cv, LX0 + 22, 224, f"{cw}×{ch}", TEXT, F_BIG)
        text(cv, LX0 + 22, 266, (f"{hz} Hz  ·  native {nw}×{nh}" if hz else f"native {nw}×{nh}"), SUB, F_S)
        lab = "STRETCHED" if stretched else "NATIVE"
        w = tw(lab, F_XS) + 24
        rrect(cv, LX1 - 18 - w, 168, LX1 - 18, 190, 11, ACCENT if stretched else "", outline="" if stretched else SUB)
        text(cv, LX1 - 18 - w / 2, 179, lab, ON_ACCENT if stretched else SUB, F_XS, "center")
        # custom resolution
        self.card(LX0, 300, LX1, 430)
        text(cv, LX0 + 22, 318, "Custom resolution", MUTED, F_S)
        ey = 336
        rrect(cv, LX0 + 18, ey, LX0 + 98, ey + 36, 6, INPUT, outline=STROKE)
        cv.create_window(LX0 + 28, ey + 8, window=self.ew, anchor="nw", width=60, height=20, tags="ui")
        text(cv, LX0 + 112, ey + 18, "×", MUTED, F_H, "center")
        rrect(cv, LX0 + 126, ey, LX0 + 206, ey + 36, 6, INPUT, outline=STROKE)
        cv.create_window(LX0 + 136, ey + 8, window=self.eh, anchor="nw", width=60, height=20, tags="ui")
        hl = f"{self.hz} Hz" if self.hz else "Auto Hz"
        btn(cv, sf, LX0 + 214, ey, LX1 - 14, ey + 36, hl, self.cycle_hz, "pri")
        text(cv, LX0 + 22, 396, "Click Hz to change the refresh rate.", MUTED, F_XS)
        text(cv, LX0 + 22, 412, "Pick a preset or type your own size.", MUTED, F_XS)
        # crosshair scaling
        self.card(LX0, 440, LX1, 668)
        text(cv, LX0 + 22, 458, "Crosshair on any resolution", MUTED, F_S)
        for i, (key, title, desc) in enumerate(SCALE_MODES):
            y = 490 + i * 50
            on = self.prefs["scale_mode"] == key
            cv.create_oval(LX0 + 22, y - 9, LX0 + 40, y + 9, outline=ACCENT if on else MUTED, width=2, tags="ui")
            if on:
                cv.create_oval(LX0 + 26, y - 5, LX0 + 36, y + 5, fill=ACCENT, outline="", tags="ui")
            text(cv, LX0 + 52, y - 6, title, TEXT, F_B)
            text(cv, LX0 + 52, y + 11, desc, MUTED, F_XS)
            sf.add((LX0 + 16, y - 20, LX1 - 12, y + 26), click=lambda px, py, k=key: self.set_pref("scale_mode", k))
        toggle(cv, sf, LX0 + 22, 636, "Restore native resolution on exit", bool(self.prefs["restore_exit"]),
               lambda: self.set_pref("restore_exit", not self.prefs["restore_exit"]))
        # presets
        self.card(RX0, 156, RX1, 528)
        text(cv, RX0 + 22, 174, "Stretch presets", MUTED, F_S)
        try:
            cur_pick = (int(self.vw.get()), int(self.vh.get()))
        except ValueError:
            cur_pick = None
        if not DISPLAY_OK:
            text(cv, RX0 + 22, 214, "Resolution changes work on", TEXT, F_M)
            text(cv, RX0 + 22, 234, "Windows only.", TEXT, F_M)
        elif not self.presets:
            text(cv, RX0 + 22, 214, "No stretch presets found.", TEXT, F_M)
            text(cv, RX0 + 22, 234, "Type a size on the left.", MUTED, F_S)
        for i, (w, h) in enumerate(self.presets):
            y = 190 + i * 42
            on = cur_pick == (w, h)
            rrect(cv, RX0 + 14, y, RX1 - 14, y + 36, 6, HERO if on else CARD2, outline=ACCENT if on else "")
            text(cv, RX0 + 34, y + 18, f"{w} × {h}", TEXT, F_B)
            text(cv, RX1 - 34, y + 18, ratio(w, h), ACCENT if on else MUTED, F_B, "e")
            sf.add((RX0 + 14, y, RX1 - 14, y + 36), click=lambda px, py, w=w, h=h: self.pick_res(w, h))
        # actions
        self.card(RX0, 538, RX1, 668)
        btn(cv, sf, RX0 + 16, 554, RX0 + 146, 592, "Apply", self.apply_stretch, "pri")
        btn(cv, sf, RX0 + 154, 554, RX1 - 16, 592, "Back to native", self.go_native)
        for i, ln in enumerate(("Tip: in your game pick the same", "resolution and set GPU scaling to",
                                "“Full-screen” in the NVIDIA / AMD", "control panel.")):
            text(cv, RX0 + 22, 612 + i * 14, ln, MUTED, F_XS)

    # ---------- games ----------
    def g_refresh(self):
        p = self.prefs
        p.setdefault("g_users", {})
        p.setdefault("g_sel", None)
        self.scan = {}
        try:
            self.installed = scan_installed(self.scan) if WIN else {}
        except Exception as e:
            self.installed = {}
            self.scan = dict(error=f"Scan failed ({e.__class__.__name__}: {e})")

    def g_scroll(self, delta):
        self.g_off += -1 if delta > 0 else 1
        self.render()

    def g_mode_set(self, m):
        self.g_mode, self.g_off = m, 0
        self.render()

    def g_select(self, name):
        self.g_off = 0
        self.set_pref("g_sel", name)

    def page_games(self):
        cv, sf, p = self.c, self.sf, self.prefs
        if not WIN:
            self.card(100, 156, 972, 668)
            text(cv, 124, 192, "Games only works on Windows.", TEXT, F_H)
            return
        users = list(p["g_users"])
        sel = p.get("g_sel")
        if sel not in p["g_users"]:
            sel = p["g_sel"] = users[0] if users else None
        # users
        self.card(100, 156, 350, 668)
        text(cv, 122, 176, "Users", MUTED, F_S)
        if not users:
            text(cv, 122, 208, "No users yet.", TEXT, F_M)
            text(cv, 122, 230, "Press Add user to log in", MUTED, F_XS)
            text(cv, 122, 246, "with an Epic account.", MUTED, F_XS)
        for i, name in enumerate(users[:9]):
            y, on = 192 + i * 46, name == sel
            rrect(cv, 112, y, 338, y + 40, 6, HERO if on else CARD2, outline=ACCENT if on else "")
            text(cv, 128, y + 20, fit(name, F_B, 100), TEXT, F_B)
            text(cv, 326, y + 20, fit(p["g_users"][name].get("display", ""), F_XS, 85), MUTED, F_XS, "e")
            sf.add((112, y, 338, y + 40), click=lambda px, py, n=name: self.g_select(n))
        btn(cv, sf, 112, 620, 222, 654, "Add user", self.g_add_user, "pri", font=F_M)
        btn(cv, sf, 230, 620, 338, 654, "Remove", self.g_remove_user, "sec", font=F_M)
        # games
        self.card(364, 156, 972, 668)
        text(cv, 386, 177, fit(f"{sel}'s games" if sel else "Games", F_H, 280), TEXT, F_H)
        btn(cv, sf, 972 - 14 - 90, 162, 972 - 14, 192, "All", lambda: self.g_mode_set("all"),
            "pri" if self.g_mode == "all" else "sec", font=F_M)
        btn(cv, sf, 972 - 14 - 90 - 6 - 100, 162, 972 - 110, 192, "Installed", lambda: self.g_mode_set("inst"),
            "pri" if self.g_mode != "all" else "sec", font=F_M)
        inst = self.installed
        rows = []
        if sel:
            rows = [g for g in p["g_users"][sel].get("library", [])
                    if self.g_mode == "all" or g[0].lower() in inst]
            rows.sort(key=lambda g: (g[0].lower() not in inst, g[1].lower()))
        n, vis, RH, Y0 = len(rows), 7, 56, 204
        self.g_off = max(0, min(self.g_off, max(0, n - vis)))
        sf.add((364, Y0, 972, Y0 + vis * RH), wheel=self.g_scroll, cursor="")
        if not sel:
            text(cv, 386, Y0 + 14, "Add a user first. Their games show up here.", MUTED, F_M)
        elif not rows:
            text(cv, 386, Y0 + 14, "No installed games found for this user.", MUTED, F_M)
            text(cv, 386, Y0 + 36, "Press All to see everything they own, or Refresh library.", MUTED, F_XS)
            sc = self.scan
            note = sc.get("error") or (f"Epic manifests found: {sc.get('files', 0)}, usable games: {len(inst)}"
                                       + (f", unreadable: {sc['unreadable']}" if sc.get("unreadable") else ""))
            text(cv, 386, Y0 + 62, fit(note, F_XS, 560), DIM, F_XS)
            sk = ", ".join(f"{k} ({v})" for k, v in list(sc.get("skipped", {}).items())[:3])
            if sk:
                text(cv, 386, Y0 + 80, fit("Skipped: " + sk, F_XS, 560), DIM, F_XS)
        for i in range(vis):
            idx = self.g_off + i
            if idx >= n:
                break
            app, title = rows[idx]
            key = app.lower()
            y, ok = Y0 + i * RH, key in inst
            rrect(cv, 376, y, 950, y + 50, 8, CARD2, outline=STROKE)
            text(cv, 396, y + 19, fit(title, F_B, 340), TEXT, F_B)
            text(cv, 396, y + 37, fit(inst[key]["InstallLocation"] if ok else
                                      self.scan.get("skipped", {}).get(key, "Not installed").capitalize(),
                                      F_XS, 340), MUTED, F_XS)
            if ok:
                btn(cv, sf, 950 - 96, y + 10, 950 - 16, y + 40, "Launch", lambda a=app: self.g_launch(a), "pri",
                    font=F_M)
            else:
                text(cv, 950 - 20, y + 25, "Install in Epic Launcher", DIM, F_XS, "e")
        if n > vis:
            h = vis * RH - 6
            th = max(30, h * vis / n)
            ty = Y0 + (h - th) * self.g_off / (n - vis)
            rrect(cv, 958, Y0, 961, Y0 + h, 1.5, TRACK)
            rrect(cv, 958, ty, 961, ty + th, 1.5, MUTED)
        # bottom bar
        cv.create_line(376, 604, 960, 604, fill=STROKE, tags="ui")
        hint = "Press Launch. The app logs in for you, no Epic Launcher needed."
        text(cv, 386, 636, fit(self.opt_msg or hint, F_S, 400), TEXT if self.opt_msg else MUTED, F_S)
        btn(cv, sf, 960 - 150, 620, 960, 654, "Refresh library", self.g_sync, "sec", font=F_M)

    def g_add_user(self):
        if self.opt_busy:
            return
        p = self.prefs
        if len(p["g_users"]) >= 9:
            return self.opt_note("Maximum 9 users. Remove one first.")
        name = ask_text(self.root, "Name of this user (for example Main or Alt):")
        if not name or not name.strip():
            return
        name = name.strip()
        webbrowser.open(EPIC_LOGIN)
        code = ask_text(self.root, f"Log in to Epic as {name} in the browser that just opened. Use a private "
                        "window if another account is already logged in.\n\nWhen the page shows some text with "
                        "an authorizationCode, select all, copy it and paste it here:")
        if not code or not code.strip():
            return

        def job():
            tok = epic_login(code)
            a = auth_load()
            a[name] = dict(account_id=tok["account_id"], display_name=tok.get("displayName", ""),
                           refresh_token=tok["refresh_token"])
            auth_save(a)
            lib = epic_library(tok)
            p["g_users"][name] = dict(display=tok.get("displayName", ""), library=lib)
            p["g_sel"] = name
            return len(lib)

        self.opt_run(job, lambda n: f"Added {name} with {n} games")

    def g_sync(self):
        p, sel = self.prefs, self.prefs.get("g_sel")
        if not sel:
            return self.opt_note("No user selected.")

        def job():
            self.g_refresh()   # also re-checks which games are installed
            tok = epic_session(sel)
            lib = epic_library(tok)
            p["g_users"][sel]["library"] = lib
            return len(lib)

        self.opt_run(job, lambda n: f"{sel}: {n} games found")

    def g_remove_user(self):
        p, sel = self.prefs, self.prefs.get("g_sel")
        if not sel:
            return self.opt_note("No user selected.")
        if not ask_yes(self.root, f"Remove {sel}? Their login is deleted from this app (not from Epic).",
                       yes="Remove"):
            return
        a = auth_load()
        a.pop(sel, None)
        try:
            auth_save(a)
        except OSError:
            pass
        p["g_users"].pop(sel, None)
        p["g_sel"] = None
        self.redraw()

    def g_launch(self, app):
        p, sel = self.prefs, self.prefs.get("g_sel")
        if not sel or self.opt_busy:
            return
        title = next((g[1] for g in p["g_users"][sel].get("library", []) if g[0] == app), app)
        self.opt_run(lambda: launch_game(sel, app, self.installed), f"Launching {title} as {sel}")

    def page_lib(self):
        cv, sf = self.c, self.sf
        X0, X1 = 364, 972
        names = list(self.saved)
        self.card(X0, 202, X1, 668)
        text(cv, X0 + 22, 220, f"Saved crosshairs ({len(names)})", MUTED, F_S)
        vis = 8
        self.lib_off = max(0, min(self.lib_off, max(0, len(names) - vis)))
        sf.add((X0, 238, X1, 600), wheel=self.lib_scroll)
        if not names:
            text(cv, X0 + 22, 262, "Nothing saved yet. Press “Save current” to keep this crosshair.", MUTED, F_M)
        for i in range(vis):
            idx = self.lib_off + i
            if idx >= len(names):
                break
            y = 238 + i * 45
            on = idx == self.sel
            rrect(cv, X0 + 16, y, X1 - 16, y + 39, 6, HERO if on else CARD2, outline=ACCENT if on else "")
            text(cv, X0 + 38, y + 20, names[idx], TEXT, F_B)
            icon(cv, "arrow", X1 - 40, y + 20, ACCENT if on else MUTED)
            sf.add((X0 + 16, y, X1 - 16, y + 39), click=lambda px, py, n=idx: self.select_lib(n), wheel=self.lib_scroll)
        x = X0 + 16
        for label, fn, kind in (("Save current", self.save_cur, "pri"), ("Load", self.load_sel, "sec"),
                                ("Delete", self.del_sel, "sec"), ("Copy code", self.copy_code, "sec"),
                                ("Paste code", self.paste_code, "sec")):
            w = tw(label, F_B) + 34
            btn(cv, sf, x, 618, x + w, 652, label, fn, kind)
            x += w + 6

    def opt_refresh(self):
        st = {}
        for t in TWEAKS:
            try:
                st[t["id"]] = bool(t["check"](self.prefs))
            except Exception:
                st[t["id"]] = False
        self.opt_state = st
        try:
            self.opt_start = startup_list()
        except Exception:
            self.opt_start = []

    def opt_setcat(self, k):
        self.opt_cat, self.opt_off = k, 0
        self.render()

    def opt_scroll(self, delta):
        self.opt_off += -1 if delta > 0 else 1
        self.render()

    def opt_note(self, msg):
        self.opt_msg = msg
        self.render()

    def opt_run(self, job, msg):
        """Runs `job` in the background so the window never freezes; msg(result) or a string is shown afterwards."""
        if self.opt_busy:
            return
        self.opt_busy, self.opt_msg = True, "Working..."
        self.render()
        box = {}

        def work():
            try:
                box["r"] = job()
            except Exception as e:
                box["e"] = e

        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not box:
                self.root.after(120, poll)
                return
            self.opt_busy = False
            e = box.get("e")
            if e is not None:
                self.opt_msg = "Needs administrator rights." if isinstance(e, PermissionError) else f"Failed: {e}"
            else:
                self.opt_msg = msg(box.get("r")) if callable(msg) else msg
            self.opt_refresh()
            self.info = sysinfo()
            self.redraw()

        self.root.after(120, poll)

    def opt_toggle(self, t):
        if self.opt_busy:
            return
        if t["admin"] and not is_admin():
            return self.opt_note("Needs administrator. Press “Run as administrator”.")
        p, on = self.prefs, bool(self.opt_state.get(t["id"]))
        if on:
            self.opt_run(lambda: opt_revert(t, p), "Undone: " + t["title"])
        else:
            self.opt_run(lambda: opt_apply(t, p), "Applied: " + t["title"] + (" (restart needed)" if t["reboot"] else ""))

    def opt_batch(self, todo, apply):
        adm, p = is_admin(), self.prefs
        skipped = [t for t in todo if t["admin"] and not adm]
        todo = [t for t in todo if t not in skipped]
        if not todo:
            return self.opt_note("Nothing to do." + (f" {len(skipped)} need administrator." if skipped else ""))

        def job():
            ok, bad = 0, 0
            for t in todo:
                try:
                    (opt_apply if apply else opt_revert)(t, p)
                    ok += 1
                except Exception:
                    bad += 1
            return ok, bad

        def msg(r):
            s = f"{'Applied' if apply else 'Undone'}: {r[0]} tweaks"
            if skipped:
                s += f", {len(skipped)} skipped (admin)"
            if r[1]:
                s += f", {r[1]} failed"
            if apply and any(t["reboot"] for t in todo):
                s += ". Restart needed."
            return s

        self.opt_run(job, msg)

    def opt_all(self):
        lvl = self.prefs.get("opt_prof", "bal")
        name = next(n for k, n, _ in OPT_PROFILES if k == lvl)
        todo = [t for t in profile_tweaks(lvl) if not self.opt_state.get(t["id"])]
        if not todo:
            return self.opt_note(f"The {name} profile is already fully on.")
        if messagebox.askyesno(NAME, f"Apply the {name} profile ({len(todo)} tweaks)?\n\nTip: create a restore point "
                               "first. You can undo every tweak here.", parent=self.root):
            self.opt_batch(todo, True)

    def opt_cat_all(self, apply):
        if apply:
            todo = [t for t in TWEAKS if t["cat"] == self.opt_cat and t["rec"] and not self.opt_state.get(t["id"])]
        else:
            done = self.prefs.get("opt_applied", [])
            todo = [t for t in TWEAKS if t["cat"] == self.opt_cat and t["id"] in done]
        self.opt_batch(todo, apply)

    def opt_undo_all(self):
        done = self.prefs.get("opt_applied", [])
        todo = [t for t in TWEAKS if t["id"] in done]
        if not todo:
            return self.opt_note("Nothing to undo. You haven't applied anything yet.")
        if messagebox.askyesno(NAME, f"Undo {len(todo)} tweaks you applied with this app?", parent=self.root):
            self.opt_batch(todo, False)

    def opt_restore(self):
        if not is_admin():
            return self.opt_note("A restore point needs administrator. Press “Run as administrator”.")
        self.opt_run(make_restore_point, lambda r: r)

    def opt_admin(self):
        if relaunch_admin():
            self.quit()
        else:
            self.opt_note("Administrator request was cancelled.")

    def opt_act(self, a):
        if self.opt_busy:
            return
        if a.get("confirm") and not messagebox.askyesno(NAME, a["confirm"], parent=self.root):
            return

        def done(r):
            self.opt_res[a["id"]] = r
            return a["title"] + ": " + r

        self.opt_run(lambda: a["run"](self.prefs), done)

    def opt_act_all(self):
        acts = [a for a in ACTIONS if a["cat"] == "clean" and not a.get("confirm")]

        def done(r):
            for a, res in r:
                self.opt_res[a["id"]] = res
            return "Cleanup done"

        self.opt_run(lambda: [(a, a["run"](self.prefs)) for a in acts], done)

    def opt_start_toggle(self, e):
        if self.opt_busy:
            return
        if e["hive"] == "HKLM" and not is_admin():
            return self.opt_note("This one needs administrator. Press “Run as administrator”.")
        on = not e["on"]
        self.opt_run(lambda: startup_set(e, on), ("Enabled: " if on else "Disabled: ") + e["name"])

    # ---------- overlay on the screen ----------
    def make_overlay(self):
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.attributes("-topmost", True)
        key = "#010101"
        ov.configure(bg=key)
        try:
            ov.attributes("-transparentcolor", key)
        except tk.TclError:
            pass
        self.OV = OV_SIZE
        self.ovc = tk.Canvas(ov, width=self.OV, height=self.OV, bg=key, highlightthickness=0)
        self.ovc.pack()
        self.ov = ov
        self.place_overlay()
        ov.update_idletasks()
        try:  # clicks pass through, no taskbar icon
            u = ctypes.windll.user32
            hwnd = u.GetParent(ov.winfo_id()) or ov.winfo_id()
            st = u.GetWindowLongW(hwnd, -20)
            u.SetWindowLongW(hwnd, -20, st | 0x80000 | 0x20 | 0x80)
        except Exception:
            pass

    def place_overlay(self):
        """Centers the overlay on the primary screen at whatever resolution it currently has."""
        if not self.ov:
            return
        sw, sh = screen_size() or (self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        self.ov.geometry(f"{self.OV}x{self.OV}+{(sw - self.OV) // 2}+{(sh - self.OV) // 2}")

    def draw_overlay(self):
        if not self.ov:
            return
        c = self.OV // 2
        draw(self.ovc, c, c, self.s, "xh")
        xf, yf = scale_factors(self.prefs["scale_mode"], self.cur[:2], self.native[:2])
        if abs(xf - 1) > 1e-6 or abs(yf - 1) > 1e-6:
            self.ovc.scale("xh", c, c, xf, yf)

    def tick(self):
        """Once a second: keep the overlay on top and follow resolution changes made outside the app."""
        try:
            ss = screen_size()
            if ss and ss != self.last_ss:
                self.after_res_change()
            if self.ov and self.show_ov:
                self.ov.attributes("-topmost", True)
                self.ov.lift()
        except Exception:
            pass
        self.root.after(1000, self.tick)

    def toggle_ov(self):
        self.show_ov = not self.show_ov
        if self.show_ov:
            self.ov.deiconify()
            self.ov.attributes("-topmost", True)
        else:
            self.ov.withdraw()
        self.render()

    def poll_hotkey(self):
        try:
            down = bool(ctypes.windll.user32.GetAsyncKeyState(0x77) & 0x8000)  # F8
            if down and not self.f8_down:
                self.toggle_ov()
            self.f8_down = down
        except Exception:
            pass
        self.root.after(50, self.poll_hotkey)

    # ---------- updates ----------
    def check_updates(self, manual=False):
        self._res = None

        def work():
            try:
                self._res = ("ok", check_update())
            except Exception as e:
                self._res = ("err", e)

        threading.Thread(target=work, daemon=True).start()
        self.root.after(300, lambda: self.upd_done(manual))

    def upd_done(self, manual):
        if self._res is None:
            self.root.after(300, lambda: self.upd_done(manual))
            return
        kind, d = self._res
        if kind == "err":
            if manual:
                messagebox.showerror(NAME, f"Could not check for updates.\n\nDetails: {d}\n\nAddress:\n{UPDATE_URL}",
                                     parent=self.root)
            return
        if d is None:
            if manual:
                messagebox.showinfo(NAME, f"You have the latest version (v{VERSION}).", parent=self.root)
            return
        if not messagebox.askyesno(NAME, f"A new version (v{d['version']}) is available.\nUpdate now?", parent=self.root):
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(NAME, "Auto-update only works in the installed .exe version.", parent=self.root)
            return
        try:
            apply_update(d["url"])
            self.quit()
        except Exception as e:
            messagebox.showerror(NAME, f"Update failed:\n{e}", parent=self.root)

    # ---------- logic ----------
    def show(self, k):
        self.tab, self.opt_off, self.opt_msg, self.g_off = k, 0, "", 0
        if k == "games":
            self.g_refresh()
        if k in ("dash", "opt", "start"):
            self.opt_refresh()
        if k == "dash":
            self.info = sysinfo()
        self.render()

    def xshow(self, k):
        self.xsub = k
        self.render()

    def subshow(self, k):
        self.sub = k
        self.render()

    def redraw(self):
        self.render()
        self.draw_overlay()
        save(self.s, self.saved, self.prefs)

    def redraw_xh(self):
        self.draw_preview()
        self.draw_overlay()
        save(self.s, self.saved, self.prefs)

    def set(self, k, v):
        if self.s.get(k) == v:
            return
        self.s[k] = v
        for g in ("inner", "outer"):  # keep horizontal/vertical length linked when asked
            a, b, lk = g + "_len", g + "_lenv", g + "_link"
            if k == lk and v:
                self.s[b] = self.s[a]
            elif self.s[lk] and k in (a, b):
                self.s[b if k == a else a] = v
        self.redraw()

    def set_pref(self, k, v):
        self.prefs[k] = v
        self.redraw()

    def set_pvbg(self, c):
        self.pvbg = c
        self.render()

    def set_tool(self, v):
        self.tool = v
        self.render()

    def set_flag(self, name):
        setattr(self, name, not getattr(self, name))
        self.render()

    def choose_style(self, k):
        self.s["style"] = k
        if k == "advanced":
            self.tab, self.xsub = "xh", "custom"
        elif k == "custom":
            self.tab, self.xsub = "xh", "draw"
        self.redraw()

    def preset(self, p):
        self.s.update(copy.deepcopy(p))
        self.redraw()

    def pick_color(self, key="color"):
        ask_color(self.root, self.s[key], "Color wheel", live=lambda c: self.set(key, c))

    def color_all(self):
        for key in ("inner_color", "outer_color", "cdot_color", "ring_color"):
            self.s[key] = self.s["color"]
        self.redraw()

    def paint_at(self, x, y, erase=False):
        if (self.tab, self.xsub) != ("xh", "draw") or not self.cellid:
            return
        gx, gy = self.grid_org
        i, j = int((x - gx) // CELL), int((y - gy) // CELL)
        if not (0 <= i < N and 0 <= j < N):
            return
        pts = {(i, j)}
        if self.mx:
            pts |= {(N - 1 - a, b) for a, b in pts}
        if self.my:
            pts |= {(a, N - 1 - b) for a, b in pts}
        for a, b in pts:
            k = f"{a},{b}"
            if erase or self.tool == "erase":
                self.s["pixels"].pop(k, None)
            else:
                self.s["pixels"][k] = self.s["color"]
            self.c.itemconfig(self.cellid[(a, b)], fill=self.s["pixels"].get(k, INPUT))
        self.s["style"] = "custom"
        self.redraw_xh()

    def clear_pixels(self):
        self.s["pixels"] = {}
        self.redraw()

    # ---------- library ----------
    def lib_scroll(self, delta):
        self.lib_off += -1 if delta > 0 else 1
        self.render()

    def select_lib(self, idx):
        self.sel = idx
        self.render()

    def save_cur(self):
        name = simpledialog.askstring(NAME, "Name of crosshair:", parent=self.root)
        if name and name.strip():
            self.saved[name.strip()] = copy.deepcopy(self.s)
            self.sel = list(self.saved).index(name.strip())
            self.redraw()

    def load_sel(self):
        names = list(self.saved)
        if self.sel is not None and self.sel < len(names):
            self.s = {**copy.deepcopy(DEFAULT), **copy.deepcopy(self.saved[names[self.sel]])}
            self.redraw()

    def del_sel(self):
        names = list(self.saved)
        if self.sel is not None and self.sel < len(names):
            if messagebox.askyesno(NAME, "Delete the selected crosshair?", parent=self.root):
                self.saved.pop(names[self.sel], None)
                self.sel = None
                self.redraw()

    def copy_code(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(self.s))

    def paste_code(self):
        old = self.s
        try:
            d = json.loads(self.root.clipboard_get())
            self.s = {**copy.deepcopy(DEFAULT), **d}
            self.redraw()
        except Exception:
            self.s = old
            messagebox.showerror(NAME, "No valid crosshair code found on the clipboard.", parent=self.root)

    def quit(self):
        if self.prefs.get("restore_exit") and DISPLAY_OK:
            try:
                if (self.cur[0], self.cur[1]) != (self.native[0], self.native[1]):
                    if set_mode(*self.native) != 0:
                        reset_mode()
            except Exception:
                pass
        save(self.s, self.saved, self.prefs)
        self.root.destroy()


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().root.mainloop()
