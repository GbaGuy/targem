# targem (תרגם)

Free, open-source on-screen translator for video games, for **Windows** and **Linux** (Wayland/Hyprland).
Drag a box over the game's text and a Hebrew translation appears on screen. The game keeps focus.
Works offline too.

## Windows

**Easy install:** download this repo (green *Code* button → *Download ZIP*), unzip, double-click **`install.bat`**.
Or paste into PowerShell:

```powershell
irm https://raw.githubusercontent.com/GbaGuy/targem/main/install.ps1 | iex
```

The installer sets up Python and Tesseract OCR (via winget), targem, and the offline Hebrew model, then
adds targem to the Start Menu and desktop. To remove it: `install.bat -Uninstall`.

Hotkeys work in-game:

| Keys | Action |
|---|---|
| Ctrl+Alt+T | select an area and translate |
| Ctrl+Alt+R | translate the same area again |
| Ctrl+Alt+L | live mode on/off |
| Ctrl+Alt+X | close the translation |

Run games in **borderless / windowed** mode: Windows can't draw anything over exclusive fullscreen.

## Linux

```sh
sudo pacman -S grim slurp tesseract tesseract-data-eng python-gobject gtk4-layer-shell
./targem.py --bubble
```

Other source languages: add `tesseract-data-jpn`, `-kor`, `-rus`, ... and pass `--ocr-lang eng+jpn`.

Hyprland:

```
exec-once = ~/Projects/targem/targem.py --bubble --offline
bind = SUPER, T, exec, ~/Projects/targem/targem.py --offline
bind = SUPER SHIFT, T, exec, ~/Projects/targem/targem.py --live --offline
```

Command line: `--last` (same area again), `--live` (follow the text as it changes), `--to en` (other target
language), `--font-size 40`, `--seconds N` (auto-close), `--offline` (see below).

## Using it

**The bubble (ת)** floats on top of the game. Drag it anywhere; click it for:

| Linux | Windows | |
|---|---|---|
| 🔍 | תרגם | drag over text and translate |
| ↻ | שוב | translate the same area again |
| ▶ | חי | live: keeps watching the area, the Hebrew updates as the game text changes |
| A+ / A− | A+ / A− | bigger / smaller text |
| ⌖ | למקום | put the translation box back on the text, original width |
| ✕ | סגור | close the translation |
| ⏻ | יציאה | quit |

**The translation box:**

- **drag** it anywhere: new translations show up in the same spot
- **drag the ◢ corner** to make it wider or narrower
- **mouse wheel** over it: text size; **Shift + wheel**: background transparency
- **click** it to close

Everything is remembered between runs.

## Online vs offline

| | Online (default) | Offline (`--offline`; the Windows installer uses it) |
|---|---|---|
| Engine | Google Translate (free endpoint, no key) | [Argos Translate](https://github.com/argosopentech/argos-translate) model on ctranslate2 |
| Quality | best | good on short lines, weaker on game slang |
| Speed (click to Hebrew) | ~1.5-2.5 s | under 1 s |
| Needs | internet | one-time 120 MB download |

Online mode falls back to the offline model automatically when there's no internet.

Offline setup on Linux:

```sh
uv venv --python /usr/bin/python3 --system-site-packages .venv
uv pip install --python .venv/bin/python ctranslate2 sentencepiece
./targem.py --setup-offline
```

targem switches to the venv by itself. (Argos itself isn't used: it pulls in 5 GB of PyTorch just to split
sentences.)

## Test

```sh
python3 test_targem.py
```

CI also runs the Windows UI, the offline model and an installer parse check on a real Windows machine.

## License

MIT
