"""Windows front end: tkinter bubble + overlay, Pillow screen grab. OCR cleanup and translation come from targem."""
import ctypes
import ctypes.wintypes
import io
import queue
import shutil
import subprocess
import threading
import tkinter as tk

from PIL import ImageGrab

from targem import CACHE, bump_font, bump_opacity, clean_ocr, font_size, save_settings, settings, translate

TESSERACT = shutil.which("tesseract") or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
FG, BG, ACCENT, KEY = "#ffffff", "#000000", "#ffd400", "#ff00ff"  # KEY = transparent colour for the round bubble
user32 = ctypes.windll.user32


def ocr(box, lang):
    img = ImageGrab.grab(bbox=box, all_screens=True)
    img = img.resize((img.width * 2, img.height * 2))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return subprocess.run([TESSERACT, "stdin", "stdout", "-l", lang, "--psm", "6"], input=buf.getvalue(),
                          capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode()


class App:
    def __init__(self, a):
        self.a = a
        self.ui = queue.Queue()  # worker/hotkey threads hand callables to the Tk thread
        self.box = self.overlay = self.last = None
        self.live = False
        self.root = root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True, "-transparentcolor", KEY)
        root.configure(bg=KEY)

        bubble = tk.Canvas(root, width=60, height=60, bg=KEY, highlightthickness=0, cursor="fleur")
        bubble.create_oval(3, 3, 57, 57, fill=BG, outline=ACCENT, width=3)
        bubble.create_text(30, 30, text="ת", fill=FG, font=("Segoe UI", 20, "bold"))
        bubble.pack()
        bubble.bind("<ButtonPress-1>", self.press)
        bubble.bind("<B1-Motion>", self.drag)
        bubble.bind("<ButtonRelease-1>", self.release)

        self.menu = tk.Frame(root, bg=KEY)
        for text, fn, stay in [("תרגם", self.select, False), ("שוב", self.again, False),
                               ("חי", self.toggle_live, False), ("A+", lambda: self.font(4), True),
                               ("A−", lambda: self.font(-4), True), ("למקום", self.reset_pos, False),
                               ("סגור", self.close, False), ("יציאה", root.destroy, False)]:
            # actions get the menu out of the way; A+/A- keep it open for repeated taps
            tk.Button(self.menu, text=text, width=6, font=("Segoe UI", 12, "bold"), bg=BG, fg=ACCENT,
                      activebackground=ACCENT, activeforeground=BG, relief="flat", bd=0,
                      command=lambda f=fn, keep=stay: (keep or self.menu.pack_forget(), f())).pack(pady=3)

        try:
            x, y = map(int, (CACHE / "bubble-win").read_text().split())
        except (OSError, ValueError):
            x, y = root.winfo_screenwidth() - 90, root.winfo_screenheight() // 2
        root.geometry(f"+{x}+{y}")
        self.hotkeys()
        self.poll()

    # --- bubble: drag to move, click for the menu. Native window moves are synchronous, so no ghost needed.
    def press(self, e, win=None):
        win = win or self.root
        self.start = (e.x_root, e.y_root, win.winfo_x(), win.winfo_y())
        self.moved = False

    def drag(self, e, win=None):
        sx, sy, wx, wy = self.start
        dx, dy = e.x_root - sx, e.y_root - sy
        self.moved = self.moved or abs(dx) + abs(dy) > 6
        if self.moved:
            (win or self.root).geometry(f"+{wx + dx}+{wy + dy}")

    def drop_overlay(self, _e):
        if self.moved:
            save_settings(overlay_win=[self.overlay.winfo_x(), self.overlay.winfo_y()])
        else:
            self.close()

    def release(self, _e):
        if self.moved:
            (CACHE / "bubble-win").write_text(f"{self.root.winfo_x()} {self.root.winfo_y()}")
        elif self.menu.winfo_ismapped():
            self.menu.pack_forget()
        else:
            self.menu.pack()

    # --- actions
    def select(self, then=None):
        """Dim the whole desktop and let the user drag a box."""
        self.close()
        vx, vy, vw, vh = (user32.GetSystemMetrics(i) for i in (76, 77, 78, 79))  # virtual screen = all monitors
        sel = tk.Toplevel(self.root)
        sel.overrideredirect(True)
        sel.attributes("-topmost", True, "-alpha", 0.3)
        sel.geometry(f"{vw}x{vh}+{vx}+{vy}")
        cv = tk.Canvas(sel, bg="grey", cursor="cross", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        st = {}

        def down(e):
            st.update(x=e.x_root, y=e.y_root, r=cv.create_rectangle(e.x, e.y, e.x, e.y, outline=ACCENT, width=3))

        def move(e):
            if "r" in st:
                cv.coords(st["r"], st["x"] - vx, st["y"] - vy, e.x, e.y)

        def up(e):
            sel.destroy()
            if "x" not in st:
                return
            box = (min(st["x"], e.x_root), min(st["y"], e.y_root), max(st["x"], e.x_root), max(st["y"], e.y_root))
            if box[2] - box[0] > 5 and box[3] - box[1] > 5:
                self.box = box
                self.root.after(150, then or self.again)  # let the dimmer vanish before the grab

        cv.bind("<ButtonPress-1>", down)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", up)
        sel.bind("<Escape>", lambda _e: sel.destroy())
        sel.focus_force()

    def again(self):
        if not self.box:
            return self.select()
        self.close()
        box = self.box
        self.root.after(100, lambda: self.work(lambda: self.translate_box(box), self.show))

    def toggle_live(self):
        if self.live:
            return self.close()
        if not self.box:
            return self.select(then=self.toggle_live)
        self.close()
        self.live, self.last = True, None
        self.tick()

    def tick(self):
        if not self.live:
            return
        box = self.box

        def job():
            text = clean_ocr(ocr(box, self.a.ocr_lang))
            if text and text != self.last:  # keep the old line while the game fades between lines
                self.last = text
                return translate(text, self.a.to, self.a.offline)

        def done(out):
            if out and self.live:
                self.show(out, below=True)  # below the box so the next grab doesn't read our overlay
            self.root.after(self.a.interval, self.tick)

        self.work(job, done)

    def font(self, step):
        bump_font(step)
        if self.overlay:
            self.label.config(font=("Segoe UI Semibold", -font_size(self.a)))

    def reset_pos(self):
        save_settings(overlay_win=None, box_width=None)
        if self.overlay:
            self.overlay.geometry(f"+{self.box[0]}+{self.box[1]}")
            self.label.config(wraplength=self.wrap())

    def wrap(self):
        return max(160, (settings().get("box_width") or self.box[2] - self.box[0]) - 34)

    def wheel(self, e):  # wheel: text size, Shift+wheel: transparency
        if e.state & 0x1:
            bump_opacity(0.05 if e.delta > 0 else -0.05)
            self.overlay.attributes("-alpha", settings()["opacity"])
        else:
            self.font(2 if e.delta > 0 else -2)

    def resize(self, e, phase):
        if phase == "press":
            self.rs = (e.x_root, self.label.cget("wraplength"))
        else:
            width = max(160, int(self.rs[1]) + e.x_root - self.rs[0])
            self.label.config(wraplength=width)
            if phase == "release":
                save_settings(box_width=width + 34)

    def close(self):
        self.live = False
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None

    # --- plumbing
    def translate_box(self, box):
        text = clean_ocr(ocr(box, self.a.ocr_lang))
        return translate(text, self.a.to, self.a.offline) if text else "לא זוהה טקסט"

    def work(self, job, done):
        def run():
            try:
                out = job()
            except (OSError, ImportError, subprocess.CalledProcessError) as e:
                out = f"שגיאה: {e}"
            self.ui.put(lambda: done(out))
        threading.Thread(target=run, daemon=True).start()

    def show(self, text, below=False):
        x0, y0, x1, y1 = self.box
        if not self.overlay:
            o = tk.Toplevel(self.root, bg=ACCENT)  # the 3px of yellow around the label is the border
            o.overrideredirect(True)
            o.attributes("-topmost", True)
            # Negative size = pixels, matching --font-size on Linux. Segoe UI ships with Windows and has full Hebrew.
            self.label = tk.Label(o, bg=BG, fg=FG, font=("Segoe UI Semibold", -font_size(self.a)), justify="right",
                                  padx=20, pady=10, cursor="fleur")
            self.label.pack(padx=3, pady=3)
            # drag to move (remembered), plain click to close
            self.label.bind("<ButtonPress-1>", lambda e: self.press(e, o))
            self.label.bind("<B1-Motion>", lambda e: self.drag(e, o))
            self.label.bind("<ButtonRelease-1>", self.drop_overlay)
            self.label.bind("<MouseWheel>", self.wheel)
            grip = tk.Label(o, text="◢", bg=BG, fg=ACCENT, font=("Segoe UI", 12), cursor="bottom_right_corner")
            grip.place(relx=1, rely=1, x=-4, y=-4, anchor="se")
            grip.bind("<ButtonPress-1>", lambda e: self.resize(e, "press"))
            grip.bind("<B1-Motion>", lambda e: self.resize(e, "move"))
            grip.bind("<ButtonRelease-1>", lambda e: self.resize(e, "release"))
            o.attributes("-alpha", settings().get("opacity", 0.95))
            self.overlay = o
            saved = settings().get("overlay_win")
            self.overlay.geometry("+{}+{}".format(*saved) if saved else f"+{x0}+{y1 + 6 if below else y0}")
        self.label.config(text=text, wraplength=self.wrap())
        self.root.lift()  # keep the bubble above the overlay

    def poll(self):
        while not self.ui.empty():
            self.ui.get()()
        self.root.after(50, self.poll)

    def hotkeys(self):
        keys = {0x54: self.select, 0x52: self.again, 0x4C: self.toggle_live, 0x58: self.close}  # Ctrl+Alt+T/R/L/X

        def loop():
            for i, vk in enumerate(keys):
                user32.RegisterHotKey(None, i, 0x4003, vk)  # MOD_ALT | MOD_CONTROL | MOD_NOREPEAT
            msg = ctypes.wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:  # WM_HOTKEY
                    self.ui.put(list(keys.values())[msg.wParam])

        threading.Thread(target=loop, daemon=True).start()


def main(a):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixels, so the grab matches what you selected
    except (AttributeError, OSError):
        pass
    CACHE.mkdir(parents=True, exist_ok=True)
    App(a).root.mainloop()
