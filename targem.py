#!/usr/bin/env python3
"""targem (תרגם): select a region of the screen, OCR it, show it translated to Hebrew on top."""
import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

LAYER_SHELL = "/usr/lib/libgtk4-layer-shell.so"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "targem"
MODELS = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "targem"
SETTINGS = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "targem" / "settings.json"
VENV = Path(__file__).resolve().parent / ".venv" / "bin" / "python"  # holds the offline libs, if set up

# IPv6 to Google hangs for 1-5 s on some networks; try IPv4 first, IPv6 stays as the fallback.
_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: sorted(_getaddrinfo(*a, **k), key=lambda ai: ai[0] != socket.AF_INET)


def settings():
    try:
        return json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        return {}


def save_settings(**kw):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps({**settings(), **kw}))


def font_size(a):
    return a.font_size or settings().get("font_size", 30)


def bump_font(step):
    save_settings(font_size=min(max(settings().get("font_size", 30) + step, 14), 90))


def bump_opacity(step):
    save_settings(opacity=round(min(max(settings().get("opacity", 0.9) + step, 0.2), 1.0), 2))


def clean_ocr(raw):
    """Game text boxes wrap mid-sentence: join lines, drop OCR junk lines."""
    lines = [l.strip() for l in raw.splitlines()]
    return " ".join(l for l in lines if sum(c.isalnum() for c in l) >= 2)


def parse_google(data):
    return "".join(seg[0] for seg in data[0] if seg[0])


def translate(text, to, offline=False):
    """Google when online (best quality); the local model with --offline or when there's no internet."""
    if not offline:
        try:
            return translate_online(text, to)
        except OSError:
            if not model_dir(to).exists():
                raise
    return translate_local(text, to)


def model_dir(to):
    return MODELS / f"en_{'he' if to == 'iw' else to}"


def translate_online(text, to):
    # Google's free web endpoint, no key.
    q = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": to, "dt": "t", "q": text})
    with urllib.request.urlopen(f"https://translate.googleapis.com/translate_a/single?{q}", timeout=10) as r:
        return parse_google(json.load(r))


_loaded = {}


def translate_local(text, to):
    """Offline: an Argos Translate model run straight on ctranslate2 (Argos itself drags in 5 GB of PyTorch)."""
    import ctranslate2
    import sentencepiece
    d = model_dir(to)
    if d not in _loaded:
        _loaded[d] = (ctranslate2.Translator(str(d / "model"), compute_type="int8"),
                      sentencepiece.SentencePieceProcessor(model_file=str(d / "sentencepiece.model")))
    tr, sp = _loaded[d]
    sents = split_sentences(text)  # fed several sentences at once, the model silently drops some
    out = tr.translate_batch([sp.encode(s, out_type=str) for s in sents], beam_size=2)
    return " ".join(sp.decode(o.hypotheses[0]) for o in out)


def split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?…])\s+", text) if s]


def setup_offline(to):
    """Download the English -> <to> Argos model and keep only what ctranslate2 needs."""
    code = "he" if to == "iw" else to
    with urllib.request.urlopen("https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json") as r:
        pkg = next((p for p in json.load(r) if p["from_code"] == "en" and p["to_code"] == code), None)
    if not pkg:
        sys.exit(f"no offline model for en -> {code}")
    dest = model_dir(to)
    print(f"downloading {pkg['links'][0]} ...")
    with tempfile.TemporaryFile() as f:
        # the model host 403s Python's default user agent
        with urllib.request.urlopen(urllib.request.Request(pkg["links"][0], headers={"User-Agent": "targem"})) as r:
            shutil.copyfileobj(r, f)
        with zipfile.ZipFile(f) as z:
            for name in z.namelist():
                rel = name.partition("/")[2]  # drop the top-level folder
                wanted = rel == "sentencepiece.model" or (rel.startswith("model/") and not rel.endswith("/"))
                if wanted and ".." not in rel:
                    (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dest / rel).write_bytes(z.read(name))
    print(f"offline model ready in {dest}")


def pick_region(last):
    saved = CACHE / "region"
    if last and saved.exists():
        return saved.read_text().strip()
    r = subprocess.run(["slurp"], capture_output=True, text=True)
    if r.returncode:
        sys.exit(0)  # selection cancelled
    saved.write_text(r.stdout.strip())
    return r.stdout.strip()


def grab(region):
    return subprocess.run(["grim", "-g", region, "-s", "2", "-"], capture_output=True, check=True).stdout


def read_text(png, lang):
    return subprocess.run(["tesseract", "stdin", "stdout", "-l", lang, "--psm", "6"],
                          input=png, capture_output=True, check=True).stdout.decode()


def ocr(region, lang):
    return read_text(grab(region), lang)


def translate_png(png, a):
    text = clean_ocr(read_text(png, a.ocr_lang))
    if not text:
        return text, "לא זוהה טקסט"
    try:
        return text, translate(text, a.to, a.offline)
    except (OSError, ImportError) as e:
        return text, f"שגיאת תרגום: {e}"


def _gtk():
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell
    return Gdk, GLib, Gtk, Gtk4LayerShell


def show(region, a):
    import cairo
    Gdk, GLib, Gtk, L = _gtk()

    pos, size = region.split()
    x, y = map(int, pos.split(","))
    w, h = map(int, size.split("x"))
    monitors = list(Gdk.Display.get_default().get_monitors())

    def inside(m, px, py):
        g = m.get_geometry()
        return g.x <= px < g.x + g.width and g.y <= py < g.y + g.height

    w = settings().get("box_width") or w  # once the box has been resized, keep that width
    saved = settings().get("overlay")  # [connector, x, y] once the box has been dragged somewhere
    mon = next((m for m in monitors if saved and m.get_connector() == saved[0]), None)
    if mon:
        bx, by = saved[1], saved[2]
    else:
        mon = next((m for m in monitors if inside(m, x, y)), monitors[0])
        g = mon.get_geometry()
        # On top of the text; live mode goes just under it so the next OCR pass doesn't read our own box.
        bx, by = x - g.x, y - g.y + (h + 6 if a.live else 0)

    css = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 800)

    def style(px, alpha):
        # Built to stay readable over any game scene: heavy Hebrew face, a dark outline + drop shadow on
        # every glyph, and a dark backing (only the backing fades with Shift+scroll; text stays solid).
        css.load_from_string(
            "window{background:transparent;}"
            "label.grip{color:#ffd400;font-size:18px;padding:0 4px 2px 0;}"
            f"label.box{{background:rgba(8,8,14,{alpha});border:3px solid #ffd400;border-radius:12px;"
            "font-family:'Rubik','Heebo','Noto Sans Hebrew','Open Sans',sans-serif;"
            f"font-size:{px}px;font-weight:700;line-height:1.35;color:#fff;padding:12px 20px;"
            "text-shadow:0 0 2px #000,0 0 2px #000,1px 1px 0 #000,-1px -1px 0 #000,0 2px 4px rgba(0,0,0,.9);}")

    st = {"x": bx, "y": by, "w": w, "moved": False, "mode": "move",
          "font": font_size(a), "alpha": settings().get("opacity", 0.9)}
    style(st["font"], st["alpha"])
    png = grab(region)  # before our window exists, so it can't end up in the shot

    def activate(app):
        # The surface covers the whole monitor but only the box takes input: the game gets every other
        # click, and dragging moves the box inside a surface that itself never moves (no compositor lag).
        win = Gtk.Window(application=app)
        L.init_for_window(win)
        L.set_layer(win, L.Layer.OVERLAY)
        L.set_keyboard_mode(win, L.KeyboardMode.NONE)  # the game keeps focus
        L.set_monitor(win, mon)
        L.set_exclusive_zone(win, -1)
        for e in (L.Edge.TOP, L.Edge.BOTTOM, L.Edge.LEFT, L.Edge.RIGHT):
            L.set_anchor(win, e, True)
        fixed = Gtk.Fixed()
        label = Gtk.Label(label="מתרגם…", wrap=True, xalign=1, justify=Gtk.Justification.RIGHT)
        label.add_css_class("box")
        label.set_max_width_chars(1)  # tiny natural width + width request = wraps at exactly the region's width
        label.set_size_request(w, -1)
        label.set_cursor_from_name("grab")
        label.set_tooltip_text("גרור להזזה · גלגלת: גודל טקסט · Shift+גלגלת: שקיפות · לחיצה: סגירה")
        grip = Gtk.Label(label="◢", halign=Gtk.Align.END, valign=Gtk.Align.END, tooltip_text="גרור לשינוי רוחב")
        grip.add_css_class("grip")
        grip.set_cursor_from_name("se-resize")
        frame = Gtk.Overlay(child=label)
        frame.add_overlay(grip)
        fixed.put(frame, st["x"], st["y"])
        win.set_child(fixed)

        def clip(*_):
            ok, r = frame.compute_bounds(fixed)
            if ok:
                rect = cairo.RectangleInt(int(r.get_x()), int(r.get_y()), int(r.get_width()), int(r.get_height()))
                win.get_surface().set_input_region(cairo.Region(rect))

        def watch():  # follow text growth, A+/A- from the bubble and scroll changes
            px, alpha = font_size(a), settings().get("opacity", 0.9)
            if (px, alpha) != (st["font"], st["alpha"]):
                st["font"], st["alpha"] = px, alpha
                style(px, alpha)
            clip()
            return True

        def on_begin(_g, x, y):
            ok, r = grip.compute_bounds(fixed)
            hit = ok and r.get_x() - 6 <= x <= r.get_x() + r.get_width() + 6 and r.get_y() - 6 <= y
            st.update(moved=False, mode="resize" if hit else "move")

        def on_update(_g, dx, dy):
            st["moved"] = st["moved"] or abs(dx) + abs(dy) > 6
            if not st["moved"]:
                return
            if st["mode"] == "resize":
                label.set_size_request(max(160, int(st["w"] + dx)), -1)
            else:
                fixed.move(frame, st["x"] + dx, st["y"] + dy)

        def on_end(_g, dx, dy):
            if not st["moved"]:
                return app.quit()  # a plain click closes it
            if st["mode"] == "resize":
                st["w"] = max(160, int(st["w"] + dx))
                save_settings(box_width=st["w"])
            else:
                g = mon.get_geometry()
                st["x"] = int(min(max(st["x"] + dx, 0), g.width - 60))
                st["y"] = int(min(max(st["y"] + dy, 0), g.height - 40))
                fixed.move(frame, st["x"], st["y"])
                save_settings(overlay=[mon.get_connector(), st["x"], st["y"]])
            clip()

        def on_scroll(ctl, _dx, dy):
            if ctl.get_current_event_state() & Gdk.ModifierType.SHIFT_MASK:
                bump_opacity(-0.05 if dy > 0 else 0.05)
            else:
                bump_font(-2 if dy > 0 else 2)
            watch()
            return True

        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", on_scroll)
        fixed.add_controller(scroll)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", on_begin)
        drag.connect("drag-update", on_update)
        drag.connect("drag-end", on_end)
        fixed.add_controller(drag)  # on the fixed, which never moves, so dx/dy stay exact

        if a.seconds and not a.live:
            GLib.timeout_add_seconds(a.seconds, app.quit)
        last = [None]

        def work():
            try:
                text = clean_ocr(ocr(region, a.ocr_lang))
                if text and text != last[0]:  # keep the old line while the game fades between lines
                    last[0] = text
                    GLib.idle_add(label.set_label, translate(text, a.to, a.offline))
            except (OSError, ImportError, subprocess.CalledProcessError):
                pass
            GLib.timeout_add(a.interval, tick)

        def tick():
            threading.Thread(target=work, daemon=True).start()
            return False

        def first():  # the window is already up showing "מתרגם…"; fill it in
            last[0], out = translate_png(png, a)
            GLib.idle_add(label.set_label, out)
            if a.live:
                GLib.timeout_add(a.interval, tick)

        threading.Thread(target=first, daemon=True).start()
        win.realize()
        # Until the first layout, only take input roughly where the box will be, never the whole screen.
        win.get_surface().set_input_region(cairo.Region(cairo.RectangleInt(st["x"], st["y"], w, 60)))
        win.present()
        GLib.idle_add(clip)
        GLib.timeout_add(300, watch)

    app = Gtk.Application()
    app.connect("activate", activate)
    app.run([])


def close_overlay():
    try:
        pid = int((CACHE / "pid").read_text())
        if pid != os.getpid() and b"targem" in Path(f"/proc/{pid}/cmdline").read_bytes():  # PIDs get reused
            os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def replace_previous():
    """Pressing the hotkey again replaces the old overlay."""
    close_overlay()
    (CACHE / "pid").write_text(str(os.getpid()))


def bubble(a):
    """Always-on-top floating button; click it for the actions."""
    import cairo
    Gdk, GLib, Gtk, L = _gtk()
    css = Gtk.CssProvider()
    css.load_from_string("window{background:transparent;}"
                         "button{border-radius:999px;min-width:46px;min-height:46px;padding:0;font-size:20px;"
                         "background:rgba(0,0,0,.9);color:#fff;border:2px solid #ffd400;box-shadow:none;}"
                         "button:hover{background:#ffd400;color:#000;}"
                         "label.main{min-width:52px;min-height:52px;border-radius:999px;font-size:26px;font-weight:700;"
                         "background:rgba(0,0,0,.9);color:#fff;border:2px solid #ffd400;}"
                         "label.main:hover{border-color:#fff;}")
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, 800)

    def run(*flags):
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--ocr-lang", a.ocr_lang, "--to", a.to,
                          *(["--offline"] if a.offline else []), *flags])

    display = Gdk.Display.get_default()
    monitors = list(display.get_monitors())
    st = {"mon": monitors[0], "x": None, "y": 0, "moved": False}
    try:  # last position: "<connector> <x> <y>"
        conn, x, y = (CACHE / "bubble").read_text().split()
        st.update(mon=next(m for m in monitors if m.get_connector() == conn), x=int(x), y=int(y))
    except (OSError, ValueError, StopIteration):
        pass
    if st["x"] is None:
        g = st["mon"].get_geometry()
        st.update(x=g.width - 80, y=g.height // 2)

    def activate(app):
        win = Gtk.Window(application=app)
        L.init_for_window(win)
        L.set_layer(win, L.Layer.OVERLAY)
        L.set_keyboard_mode(win, L.KeyboardMode.NONE)
        L.set_anchor(win, L.Edge.TOP, True)
        L.set_anchor(win, L.Edge.LEFT, True)

        def place():
            L.set_monitor(win, st["mon"])
            L.set_margin(win, L.Edge.LEFT, st["x"])
            L.set_margin(win, L.Edge.TOP, st["y"])

        # Moving a layer surface while dragging it lags a frame and overshoots. So the bubble stays put
        # (the pointer stays grabbed to it, so dx/dy are exact) while a ghost copy follows the pointer on a
        # transparent full-screen layer per monitor; on release the bubble jumps there once.
        ghosts = []

        def ghost(m):
            w = Gtk.Window(application=app)
            L.init_for_window(w)
            L.set_layer(w, L.Layer.OVERLAY)
            L.set_keyboard_mode(w, L.KeyboardMode.NONE)
            L.set_monitor(w, m)
            L.set_exclusive_zone(w, -1)
            for e in (L.Edge.TOP, L.Edge.BOTTOM, L.Edge.LEFT, L.Edge.RIGHT):
                L.set_anchor(w, e, True)
            fixed, lbl = Gtk.Fixed(), Gtk.Label(label="ת")
            lbl.add_css_class("main")
            fixed.put(lbl, 0, 0)
            w.set_child(fixed)
            w.realize()
            w.get_surface().set_input_region(cairo.Region())  # click-through: the drag stays on the bubble
            w.present()
            return m, w, fixed, lbl

        def target(dx, dy):
            g = st["mon"].get_geometry()
            gx, gy = g.x + st["x"] + dx, g.y + st["y"] + dy
            for m in monitors:
                mg = m.get_geometry()
                if mg.x <= gx + 28 < mg.x + mg.width and mg.y <= gy + 28 < mg.y + mg.height:
                    return m, int(min(max(gx - mg.x, 0), mg.width - 60)), int(min(max(gy - mg.y, 0), mg.height - 60))
            return st["mon"], st["x"], st["y"]  # dropped outside every monitor

        def on_update(_g, dx, dy):
            if not st["moved"] and abs(dx) + abs(dy) > 6:
                st["moved"] = True
                handle.set_opacity(0.3)
                ghosts.extend(ghost(m) for m in monitors)
            if st["moved"]:
                m, x, y = target(dx, dy)
                for gm, _w, fixed, lbl in ghosts:
                    lbl.set_visible(gm == m)
                    fixed.move(lbl, x, y)

        def on_end(_g, dx, dy):
            if not st["moved"]:
                revealer.set_reveal_child(not revealer.get_reveal_child())
                return
            while ghosts:
                ghosts.pop()[1].destroy()
            handle.set_opacity(1)
            st["mon"], st["x"], st["y"] = target(dx, dy)
            place()
            (CACHE / "bubble").write_text(f'{st["mon"].get_connector()} {st["x"]} {st["y"]}')

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        revealer = Gtk.Revealer(child=menu, transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN)
        for icon, tip, action, stay in [
            ("🔍", "תרגם אזור", run, False),
            ("↻", "תרגם שוב את אותו אזור", lambda: run("--last"), False),
            ("▶", "מצב חי: עוקב אחרי הטקסט", lambda: run("--live"), False),
            ("A+", "הגדל טקסט", lambda: bump_font(4), True),
            ("A−", "הקטן טקסט", lambda: bump_font(-4), True),
            ("⌖", "אפס מיקום וגודל של התרגום", lambda: save_settings(overlay=None, box_width=None), False),
            ("✕", "סגור תרגום", close_overlay, False),
            ("⏻", "יציאה", app.quit, False),
        ]:
            b = Gtk.Button(label=icon, tooltip_text=tip)
            # actions get the menu out of the way; A+/A- keep it open for repeated taps
            b.connect("clicked", lambda _b, f=action, keep=stay: (keep or revealer.set_reveal_child(False), f()))
            menu.append(b)
        handle = Gtk.Label(label="ת", tooltip_text="לחץ לתפריט, גרור להזזה")
        handle.add_css_class("main")
        handle.set_cursor_from_name("grab")
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", lambda *_: st.update(moved=False))
        drag.connect("drag-update", on_update)
        drag.connect("drag-end", on_end)
        handle.add_controller(drag)
        box.append(handle)
        box.append(revealer)
        win.set_child(box)
        place()
        win.present()

    app = Gtk.Application()
    app.connect("activate", activate)
    app.run([])


def main():
    p = argparse.ArgumentParser(description="On-screen OCR translator for games.")
    p.add_argument("--last", action="store_true", help="reuse the last selected region (e.g. the dialogue box)")
    p.add_argument("--ocr-lang", default="eng", help="tesseract language(s), e.g. eng+jpn")
    p.add_argument("--to", default="iw", help="target language code (default Hebrew)")
    p.add_argument("--live", action="store_true", help="keep watching the region and update as the text changes")
    p.add_argument("--interval", type=int, default=1000, help="live mode: ms between checks")
    p.add_argument("--font-size", type=int, help="translation text size in px (default: the A+/A- setting, 30)")
    p.add_argument("--bubble", action="store_true", help="floating always-on-top button with the actions")
    p.add_argument("--offline", action="store_true", help="translate with the local model only (no internet)")
    p.add_argument("--setup-offline", action="store_true", help="download the local model for --to, then exit")
    p.add_argument("--seconds", type=int, default=0, help="close after N seconds (0 = until clicked)")
    a = p.parse_args()

    if a.setup_offline:
        return setup_offline(a.to)

    if sys.platform == "win32":  # Windows always runs the bubble (with Ctrl+Alt hotkeys)
        import targem_win
        return targem_win.main(a)

    # gtk4-layer-shell must load before libwayland, so re-exec with it preloaded,
    # and under the project venv (offline libs, system GTK still visible) when there is one.
    python = str(VENV) if VENV.exists() else sys.executable
    if LAYER_SHELL not in os.environ.get("LD_PRELOAD", "") or sys.executable != python:
        os.environ["LD_PRELOAD"] = f"{LAYER_SHELL} {os.environ.get('LD_PRELOAD', '')}".strip()
        os.execv(python, [python, *sys.argv])

    CACHE.mkdir(parents=True, exist_ok=True)
    if a.bubble:
        return bubble(a)
    replace_previous()
    region = pick_region(a.last)
    show(region, a)


if __name__ == "__main__":
    main()
