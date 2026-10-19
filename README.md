<div dir="rtl">

# targem (תרגם)

[English below ↓](#english)

מתרגם חינמי בקוד פתוח שמתרגם טקסט ממשחקי וידאו לעברית, ישר על המסך.
מסמנים את הטקסט במשחק, והתרגום לעברית מופיע מעליו. המשחק נשאר בפוקוס, כך שאפשר להמשיך לשחק.
עובד ב-**Windows** וב-**Linux**, וגם בלי אינטרנט.

## התקנה ב-Windows

**הדרך הקלה:** הורידו את **[targem.msi](https://github.com/GbaGuy/targem/releases/latest/download/targem.msi)**
ולחצו עליו פעמיים. הכל כבר בפנים (גם מודל התרגום בלי אינטרנט), ולא צריך להתקין שום דבר אחר.
בסוף מופיע אייקון של targem על שולחן העבודה ובתפריט התחל.
הסרה: הגדרות ← אפליקציות ← targem ← הסר התקנה.

**דרך נוספת:** לחצו על הכפתור הירוק **Code** ואז **Download ZIP**, חלצו, ולחצו פעמיים על **`install.bat`**.
או הדביקו את השורה הזאת ב-PowerShell:

<div dir="ltr">

```powershell
irm https://raw.githubusercontent.com/GbaGuy/targem/main/install.ps1 | iex
```

</div>

הסקריפט מתקין לבד את Python ואת Tesseract (התוכנה שקוראת את הטקסט מהמסך), את targem ואת מודל התרגום.
הסרה: `install.bat -Uninstall`.

> **חשוב:** הריצו את המשחק במצב **Borderless** או **Windowed** (חלון ללא מסגרת).
> במצב מסך מלא "בלעדי" (Exclusive Fullscreen), Windows לא מאפשר לשום תוכנה להופיע מעל המשחק.

### קיצורי מקשים (עובדים גם באמצע משחק)

| מקשים | מה זה עושה |
|---|---|
| Ctrl+Alt+T | סימון אזור ותרגום |
| Ctrl+Alt+R | תרגום חוזר של אותו אזור |
| Ctrl+Alt+L | מצב חי: הפעלה / כיבוי |
| Ctrl+Alt+X | סגירת התרגום |

## התקנה ב-Linux

<div dir="ltr">

```sh
sudo pacman -S grim slurp tesseract tesseract-data-eng python-gobject gtk4-layer-shell
./targem.py --bubble
```

</div>

ב-Hyprland אפשר להפעיל את הבועה אוטומטית ולהוסיף קיצורי מקשים:

<div dir="ltr">

```
exec-once = ~/Projects/targem/targem.py --bubble --offline
bind = SUPER, T, exec, ~/Projects/targem/targem.py --offline
bind = SUPER SHIFT, T, exec, ~/Projects/targem/targem.py --live --offline
```

</div>

## איך משתמשים

### הבועה (ת)

עיגול שחור עם ת' שצף מעל המשחק. **גוררים** אותו לאן שרוצים, ו**לוחצים** עליו כדי לפתוח את התפריט:

| Linux | Windows | מה זה עושה |
|---|---|---|
| 🔍 | תרגם | גוררים מלבן מעל הטקסט ומקבלים תרגום |
| ↻ | שוב | מתרגם שוב את אותו אזור (בלי לסמן מחדש) |
| ▶ | חי | מצב חי: עוקב אחרי האזור, והתרגום מתעדכן כשהטקסט במשחק משתנה |
| A+ / A− | A+ / A− | הגדלה / הקטנה של הטקסט |
| ⌖ | למקום | מחזיר את תיבת התרגום למקום הטקסט ולרוחב המקורי |
| ✕ | סגור | סגירת התרגום |
| ⏻ | יציאה | יציאה מהתוכנה |

**טיפ למשחקים עם תיבת דיאלוג:** סמנו פעם אחת את תיבת הדיאלוג עם **▶ חי**, ומשם התרגום מתעדכן לבד בכל שורה חדשה.

### תיבת התרגום

- **גרירה:** מזיזים את התיבה לאן שרוצים. התרגומים הבאים יופיעו באותו מקום.
- **גרירת הפינה הצהובה ◢:** משנה את רוחב התיבה.
- **גלגלת העכבר מעל התיבה:** גודל הטקסט.
- **Shift + גלגלת:** שקיפות הרקע.
- **לחיצה:** סוגרת את התיבה.

כל ההגדרות נשמרות לפעם הבאה.

## עם אינטרנט או בלי

| | עם אינטרנט (ברירת מחדל) | בלי אינטרנט (`--offline`, ההתקנה ל-Windows משתמשת בזה) |
|---|---|---|
| מנוע | Google Translate (חינמי, בלי מפתח) | מודל של [Argos Translate](https://github.com/argosopentech/argos-translate) |
| איכות | הכי טובה | טובה במשפטים קצרים, פחות טובה בסלנג של משחקים |
| מהירות | 1.5–2.5 שניות | פחות משנייה |
| דורש | חיבור לאינטרנט | הורדה חד-פעמית של 120MB |

במצב הרגיל, אם אין אינטרנט, targem עובר לבד למודל המקומי (אם הוא מותקן).

התקנת המצב בלי אינטרנט ב-Linux:

<div dir="ltr">

```sh
uv venv --python /usr/bin/python3 --system-site-packages .venv
uv pip install --python .venv/bin/python ctranslate2 sentencepiece
./targem.py --setup-offline
```

</div>

## אפשרויות נוספות (שורת פקודה)

| אפשרות | מה זה עושה |
|---|---|
| `--last` | תרגום חוזר של אותו אזור |
| `--live` | מצב חי |
| `--offline` | תרגום רק עם המודל המקומי |
| `--font-size 40` | גודל טקסט (למסך גדול / טלוויזיה) |
| `--to en` | תרגום לשפה אחרת |
| `--ocr-lang eng+jpn` | קריאת טקסט בשפות נוספות (צריך להתקין את חבילת השפה של Tesseract) |
| `--seconds 10` | סגירה אוטומטית אחרי כמה שניות |

## בעיות נפוצות

- **התרגום לא מופיע מעל המשחק (Windows):** העבירו את המשחק למצב Borderless / Windowed.
- **התרגום יוצא משובש:** סמנו רק את הטקסט עצמו, בלי חלקים של הממשק מסביב.
- **הטקסט קטן או גדול מדי:** גלגלת העכבר מעל התיבה, או A+ / A− בבועה.
- **התרגום בלי אינטרנט לא מדויק:** זה מודל קטן. כשיש אינטרנט, הפעילו בלי `--offline` לאיכות הכי טובה.

## רישיון

MIT: חינמי לשימוש, לשינוי ולהפצה.

</div>

---

<a id="english"></a>

# English

Free, open-source on-screen translator for video games, for **Windows** and **Linux** (Wayland/Hyprland).
Drag a box over the game's text and a Hebrew translation appears on screen. The game keeps focus.
Works offline too.

## Windows

**Easy install:** download **[targem.msi](https://github.com/GbaGuy/targem/releases/latest/download/targem.msi)** and
double-click it. Everything is inside (Tesseract and the offline Hebrew model too), nothing else to install.
Remove it from Settings → Apps.

**Or, with the script:** download this repo (green *Code* button → *Download ZIP*), unzip, double-click
**`install.bat`**, or paste into PowerShell:

```powershell
irm https://raw.githubusercontent.com/GbaGuy/targem/main/install.ps1 | iex
```

The script sets up Python and Tesseract OCR (via winget), targem, and the offline Hebrew model, then
adds a targem icon to the desktop and Start Menu. To remove it: `install.bat -Uninstall`.

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

CI also runs the Windows UI, the offline model and an installer parse check on a real Windows machine,
and builds and test-installs `targem.msi`. Push a `vX.Y` tag to publish it as a release.

## License

MIT
