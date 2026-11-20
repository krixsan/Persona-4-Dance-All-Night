#!/usr/bin/env python3
"""Persona 4: Dancing All Night — Canvas PC Launcher (Sengoku Basara 4 Sumeragi Style)."""

import contextlib
import ctypes
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

def _resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve().parent
    return here.parent if here.name.lower() == "launcher" else here


FROZEN = getattr(sys, "frozen", False)
BASE_DIR = _resolve_base_dir()
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
ASSETS_DIR = (
    (BASE_DIR / "assets")
    if (BASE_DIR / "assets").is_dir()
    else (
        (BASE_DIR / "launcher" / "assets")
        if (BASE_DIR / "launcher" / "assets").is_dir()
        else (BUNDLE_DIR / "assets")
    )
)
SCRIPTS_DIR = (BASE_DIR / "scripts") if (BASE_DIR / "scripts").is_dir() else (BUNDLE_DIR / "scripts")
TOOLS_DIR = BASE_DIR / "tools"
OUT_DIR = BASE_DIR / "out"
USER_DIR = BASE_DIR / "user"
DLC_DIR = BASE_DIR / "dlc"
INI_PATH = BASE_DIR / "bbport.ini"
PREFS_PATH = BASE_DIR / "launcher_prefs.json"
LOG_PATH = BASE_DIR / "last_run.log"
DEFAULT_APP0 = BASE_DIR.parent / "Persona 4" / "00_GAME_DUMP" / "CUSA12112" / "app0" / "uroot"


def resolve_engine_exe() -> Path:
    for cand in (
        BASE_DIR / "p4dan_pc.exe",
        BASE_DIR / "sacredfire.exe",
        BASE_DIR / "out" / "sacredfire.exe",
        BASE_DIR / "out" / "gpu" / "sacredfire.exe",
    ):
        if cand.is_file():
            return cand
    return BASE_DIR / "p4dan_pc.exe"

WIDTH, HEIGHT = 960, 660
FONT_FAMILY = "Segoe UI"
COLOR_BG_DARK = "#0B0818"
COLOR_GOLD = "#F5D000"
COLOR_GOLD_BRIGHT = "#FFE600"
COLOR_MAGENTA = "#D81B60"
COLOR_CYAN = "#00E5FF"
COLOR_TEXT_WHITE = "#FFFFFF"
COLOR_TEXT_SUB = "#B9B3D6"
COLOR_TEXT_MUTED = "#9892B5"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

TEXTS = {
    "id": {
        "lang_badge": "🌐 Indonesia ▾",
        "subtitle": "Runtime Native x86_64 & Mesin Vulkan 1.3",
        "sec_res": "RESOLUSI LAYAR",
        "sec_fps": "TARGET FRAME RATE",
        "sec_upscaler": "MODE UPSCALER",
        "sec_aspect": "ASPEK RASIO",
        "sec_prefs": "PREFERENSI ENGINE",
        "sharpness": "KETAJAMAN: {val}%",
        "t_full_t": "Layar Penuh Tanpa Tepi",
        "t_full_s": "Tampilan borderless fullscreen",
        "t_sharpen_t": "Penajaman Gambar (RCAS)",
        "t_sharpen_s": "Penajaman tepi & kontras",
        "t_async_t": "Kompilasi Shader Async",
        "t_async_s": "Kurangi stutter saat transisi",
        "t_fps_t": "Overlay FPS di Game",
        "t_fps_s": "Menu & metrik (Insert / L3+R3)",
        "t_fg_t": "FSR 3 Frame Generation",
        "t_fg_s": "Interpolasi frame untuk 60+ FPS",
        "t_msaa_t": "Anti-Aliasing MSAA",
        "t_msaa_s": "Haluskan tepi objek 3D",
        "lbl_prio": "PRIORITAS",
        "prio_norm": "Normal",
        "prio_above": "Atas",
        "prio_high": "Tinggi",
        "btn_auto": "✨ Auto-Optimize",
        "btn_art_0": "🎨 Art: All-Stars",
        "btn_art_1": "🎨 Art: Disco",
        "btn_pad": "🎮 Kontrol",
        "btn_save": "💾 Save Data",
        "btn_log": "📁 Log",
        "btn_dir": "📂 Folder Game",
        "btn_shot": "📸 Screenshot",
        "shot_saved": "Screenshot tersimpan: {name}",
        "shot_folder": "Folder Screenshot dibuka (di game: tekan F12 atau klik Screenshot)",
        "play": "MAINKAN GAME",
        "preparing": "MENYIAPKAN...",
        "running": "SEDANG BERJALAN...",
        "missing": "PILIH DUMP GAME",
    },
    "en": {
        "lang_badge": "🌐 English ▾",
        "subtitle": "Native x86_64 Runtime & Vulkan 1.3 Engine",
        "sec_res": "DISPLAY RESOLUTION",
        "sec_fps": "TARGET FRAME RATE",
        "sec_upscaler": "UPSCALER MODE",
        "sec_aspect": "ASPECT RATIO",
        "sec_prefs": "ENGINE PREFERENCES",
        "sharpness": "SHARPNESS: {val}%",
        "t_full_t": "Borderless Fullscreen",
        "t_full_s": "Full screen without borders",
        "t_sharpen_t": "Image Sharpening (RCAS)",
        "t_sharpen_s": "Crisp edge & contrast boost",
        "t_async_t": "Async Shader Compile",
        "t_async_s": "Reduce shader compilation stutter",
        "t_fps_t": "In-Game FPS Overlay",
        "t_fps_s": "Menu & metrics (Insert / L3+R3)",
        "t_fg_t": "FSR 3 Frame Generation",
        "t_fg_s": "Smooth motion interpolation",
        "t_msaa_t": "MSAA Anti-Aliasing",
        "t_msaa_s": "Smooth 3D geometry edges",
        "lbl_prio": "PRIORITY",
        "prio_norm": "Normal",
        "prio_above": "Above",
        "prio_high": "High",
        "btn_auto": "✨ Auto-Optimize",
        "btn_art_0": "🎨 Art: All-Stars",
        "btn_art_1": "🎨 Art: Disco",
        "btn_pad": "🎮 Controls",
        "btn_save": "💾 Save Data",
        "btn_log": "📁 Logs",
        "btn_dir": "📂 Game Folder",
        "btn_shot": "📸 Screenshot",
        "shot_saved": "Screenshot saved: {name}",
        "shot_folder": "Screenshots folder opened (in-game: press F12 or click Screenshot)",
        "play": "PLAY GAME",
        "preparing": "PREPARING...",
        "running": "RUNNING...",
        "missing": "SELECT GAME DUMP",
    },
}


def enable_dark_titlebar(root: tk.Tk):
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def load_ini(path: Path) -> tuple[list[str], dict[str, str]]:
    if not path.is_file():
        return [], {}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    vals: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    return lines, vals


def save_ini(path: Path, updates: dict[str, str]) -> None:
    lines, _ = load_ini(path)
    rem = dict(updates)
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in line:
            k = line.partition("=")[0].strip()
            if k in rem:
                out.append(f"{k}={rem.pop(k)}")
                continue
        out.append(line)
    if not out:
        out.append("# Persona 4: Dancing All Night PC Settings")
    for k, v in rem.items():
        out.append(f"{k}={v}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def load_prefs() -> dict[str, str]:
    if PREFS_PATH.is_file():
        try:
            return json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_prefs(prefs: dict[str, str]) -> None:
    try:
        PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except Exception:
        pass


def unwrap_game_dir(p: Path) -> Path:
    """Resolve user-selected root (CUSA12112, app0, or uroot) to actual uroot/app0 folder."""
    for cand in (p, p / "uroot", p / "app0" / "uroot", p / "app0", p / "CUSA12112" / "app0" / "uroot"):
        if (cand / "eboot.bin").is_file() and (cand / "data" / "ps4.cpk").is_file():
            return cand
    return p


def validate_game_dir(p: Path) -> list[str]:
    required = [
        ("eboot.bin", "eboot.bin"),
        ("data/ps4.cpk", r"data\ps4.cpk"),
        ("data/data.cpk", r"data\data.cpk"),
        ("sce_module/libc.prx", r"sce_module\libc.prx"),
        ("sce_module/libSceFios2.prx", r"sce_module\libSceFios2.prx"),
        ("sce_sys/param.sfo", r"sce_sys\param.sfo"),
    ]
    return [label for rel, label in required if not (p / rel).is_file()]


def resolve_app0(prefs: dict[str, str]) -> Path:
    candidates: list[Path] = []
    same_home = prefs.get("launcher_dir", "").lower() == str(BASE_DIR).lower()
    saved_raw = prefs.get("app0_dir", "")
    if saved_raw and (same_home or not Path(saved_raw).is_absolute()):
        p = Path(saved_raw)
        candidates.append(p if p.is_absolute() else (BASE_DIR / p))

    candidates.extend([
        BASE_DIR / "game_data",
        BASE_DIR / "CUSA12112",
        BASE_DIR / "00_GAME_DUMP" / "CUSA12112",
        BASE_DIR.parent / "CUSA12112",
        BASE_DIR.parent / "00_GAME_DUMP" / "CUSA12112",
        DEFAULT_APP0,
    ])
    for raw in candidates:
        c = unwrap_game_dir(raw)
        if not validate_game_dir(c):
            return c
    return BASE_DIR / "game_data"


def check_vulkan_ok() -> bool:
    try:
        ctypes.WinDLL("vulkan-1.dll")
        return True
    except Exception:
        return False


def boot_files_ready() -> bool:
    return all((OUT_DIR / f).is_file() for f in ("boot-linked.bin", "content.bin", "import_names.txt", "patches.bin"))


def sync_assets_from_dump(game_dir: Path) -> None:
    sce_sys = game_dir / "sce_sys"
    target = (BASE_DIR / "launcher" / "assets") if ((BASE_DIR / "launcher").is_dir() and not FROZEN) else (BASE_DIR / "assets")
    target.mkdir(parents=True, exist_ok=True)
    for name in ("icon0.png", "pic0.png", "pic1.png"):
        src = sce_sys / name
        dst = target / name
        if src.is_file() and not dst.is_file():
            shutil.copy2(src, dst)


def run_auto_prepare(game_dir: Path, log_cb) -> None:
    """Auto-generate out/boot-linked.bin, import_names.txt, content.bin, patches.bin from PS4 dump."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p_dir in (SCRIPTS_DIR, TOOLS_DIR):
        p_str = str(p_dir)
        if p_dir.is_dir() and p_str not in sys.path:
            sys.path.insert(0, p_str)

    class _Stream:
        def write(self, msg: str):
            if msg:
                log_cb(msg)
        def flush(self):
            pass

    stream = _Stream()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        import content_profile
        import gen_import_names
        import link_libc
        import link_modules
        import patches
        import prepare

        log_cb("[SETUP] 1/5 Preparing decrypted eboot & ELF headers...\n")
        prepare.prepare(game_dir, OUT_DIR)
        log_cb("[SETUP] 2/5 Linking libc.prx...\n")
        link_libc.link(game_dir, OUT_DIR)
        log_cb("[SETUP] 3/5 Linking libSceFios2.prx...\n")
        link_modules.link(game_dir, OUT_DIR, ["libc.prx", "libSceFios2.prx"])
        log_cb("[SETUP] 4/5 Generating host import symbol table...\n")
        link_data = json.loads((OUT_DIR / "link.json").read_text(encoding="utf-8"))
        names = gen_import_names.aerolib_names(OUT_DIR / "aerolib.inl")
        lines = gen_import_names.generate(link_data["unresolved_imports"], names)
        (OUT_DIR / "import_names.txt").write_text(
            "# NID library symbol (generated by launcher auto-setup)\n" + "\n".join(lines) + "\n",
            encoding="utf-8",
        )
        log_cb("[SETUP] 5/5 Building AppContent profile & patches.bin...\n")
        content_profile.prepare(game_dir, OUT_DIR, "full", DLC_DIR if DLC_DIR.is_dir() else None)
        patches.write_blob(OUT_DIR, [])
        sync_assets_from_dump(game_dir)
        log_cb("[SETUP] First-time setup complete! Launching game...\n")


def detect_gpu_short() -> str:
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name"],
            capture_output=True, text=True, timeout=3, creationflags=NO_WINDOW,
        )
        name = res.stdout.strip()
        if name:
            return name.replace("NVIDIA GeForce ", "")
    except Exception:
        pass
    return "Vulkan GPU"


class P4BasaraStyleLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Persona 4: Dancing All Night — PC Native Port")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG_DARK)

        self.prefs = load_prefs()
        self.lang = self.prefs.get("lang", "id")
        if self.lang not in ("id", "en"):
            self.lang = "id"
        self.artwork_key = self.prefs.get("artwork", "pic0")
        if self.artwork_key not in ("pic0", "pic1"):
            self.artwork_key = "pic0"
        self.app0_dir = resolve_app0(self.prefs)
        self.gpu_name = detect_gpu_short()
        self.vulkan_ok = check_vulkan_ok()
        self.preparing = False

        self.proc: subprocess.Popen | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.log_window: tk.Toplevel | None = None
        self.log_text: scrolledtext.ScrolledText | None = None
        self.log_buffer: list[str] = []

        self._apply_window_icon()
        self._load_config()
        self._generate_textures()
        self._build_canvas()
        self.refresh_controls()
        enable_dark_titlebar(self)
        self._apply_win32_hicon()
        self._center_on_screen()
        self._poll_logs()

    def tr(self, key: str, **kw) -> str:
        t = TEXTS[self.lang].get(key, key)
        return t.format(**kw) if kw else t

    def _apply_window_icon(self):
        ico = ASSETS_DIR / "p4dan.ico"
        png = ASSETS_DIR / "icon0.png"
        if ico.is_file():
            try:
                self.iconbitmap(default=str(ico))
            except Exception:
                pass
        if png.is_file():
            try:
                self._win_icon = ImageTk.PhotoImage(Image.open(png).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS))
                self.iconphoto(True, self._win_icon)
            except Exception:
                pass

    def _apply_win32_hicon(self):
        ico = ASSETS_DIR / "p4dan.ico"
        if not ico.is_file():
            return
        try:
            self.update_idletasks()
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            # IMAGE_ICON=1, LR_LOADFROMFILE=0x0010, WM_SETICON=0x0080
            user32.LoadImageW.restype = ctypes.c_void_p
            user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
            self._hicon_sm = user32.LoadImageW(None, str(ico), 1, 16, 16, 0x0010)
            self._hicon_lg = user32.LoadImageW(None, str(ico), 1, 64, 64, 0x0010)
            if self._hicon_sm:
                user32.SendMessageW(hwnd, 0x0080, 0, self._hicon_sm)
                user32.SetClassLongPtrW(hwnd, -34, self._hicon_sm)
            if self._hicon_lg:
                user32.SendMessageW(hwnd, 0x0080, 1, self._hicon_lg)
                user32.SetClassLongPtrW(hwnd, -14, self._hicon_lg)
        except Exception:
            pass

    def _center_on_screen(self):
        self.update_idletasks()
        x = max(0, (self.winfo_screenwidth() - WIDTH) // 2)
        y = max(0, (self.winfo_screenheight() - HEIGHT) // 2 - 20)
        self.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    def _load_config(self):
        _, ini = load_ini(INI_PATH)
        self.res_val = ini.get("output_res", "1920x1080")
        if self.res_val not in ("1280x720", "1920x1080", "2560x1440", "3840x2160"):
            self.res_val = "1920x1080"
        self.fps_val = ini.get("fps_limit", "60")
        if self.fps_val not in ("60", "90", "120", "144", "0"):
            self.fps_val = "60"
        self.upscaler_val = ini.get("temporal", "fsr1")
        if self.upscaler_val not in ("off", "fsr1", "fsr3", "dlss"):
            self.upscaler_val = "fsr1"
        self.aspect_val = ini.get("aspect_ratio", "16:9")
        if self.aspect_val not in ("16:9", "21:9", "32:9"):
            self.aspect_val = "16:9"
        try:
            self.sharp_val = max(0, min(100, int(round(float(ini.get("sharpness", "0.30")) * 100))))
        except Exception:
            self.sharp_val = 30
        self.full_val = ini.get("fullscreen", "0") == "1"
        self.sharpen_val = ini.get("sharpen", "1") == "1"
        self.async_val = ini.get("async_pipelines", "1") == "1"
        self.show_fps_val = ini.get("show_fps", "1") == "1"
        self.fg_val = ini.get("framegen", "off") == "fsr3"
        self.msaa_val = ini.get("msaa", "0") == "1"
        self.prio_val = self.prefs.get("priority", "high")
        if self.prio_val not in ("normal", "above_normal", "high"):
            self.prio_val = "high"

    def _sync_ini(self):
        save_ini(
            INI_PATH,
            {
                "menu_language": "en",
                "output_res": self.res_val,
                "fps_limit": self.fps_val,
                "temporal": self.upscaler_val,
                "aspect_ratio": self.aspect_val,
                "sharpen": "1" if self.sharpen_val else "0",
                "sharpness": f"{self.sharp_val / 100.0:.2f}",
                "fsr3_sharpness": f"{self.sharp_val / 100.0:.2f}",
                "fullscreen": "1" if self.full_val else "0",
                "async_pipelines": "1" if self.async_val else "0",
                "show_fps": "1" if self.show_fps_val else "0",
                "framegen": "fsr3" if self.fg_val else "off",
                "msaa": "1" if self.msaa_val else "0",
                "patch_60fps": "1",
            },
        )
        try:
            saved_app0 = str(self.app0_dir.relative_to(BASE_DIR))
        except ValueError:
            saved_app0 = str(self.app0_dir)
        self.prefs.update({
            "lang": self.lang,
            "artwork": self.artwork_key,
            "launcher_dir": str(BASE_DIR),
            "app0_dir": saved_app0,
            "priority": self.prio_val,
        })
        save_prefs(self.prefs)

    def _create_pill_tex(self, w: int, h: int, fill, outline, radius=6, width=1) -> ImageTk.PhotoImage:
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill, outline=outline, width=width)
        return ImageTk.PhotoImage(img)

    def _create_pill_set(self, w: int, h: int):
        # Vibrant Persona 4 Dancing Magenta + Yellow-Gold outline active pill
        act = self._create_pill_tex(w, h, (175, 22, 88, 255), (255, 226, 40, 255), radius=6, width=1)
        inact = self._create_pill_tex(w, h, (30, 27, 50, 228), (68, 63, 102, 255), radius=6, width=1)
        hov = self._create_pill_tex(w, h, (46, 42, 76, 242), (112, 102, 160, 255), radius=6, width=1)
        return act, inact, hov

    def _create_switch_tex(self, on: bool) -> ImageTk.PhotoImage:
        w, h = 40, 20
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if on:
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(185, 22, 92, 255), outline=(255, 226, 40, 255), width=1)
            d.ellipse([w - 17, 3, w - 5, 15], fill=(255, 255, 255, 255))
        else:
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(32, 29, 54, 230), outline=(72, 68, 108, 255), width=1)
            d.ellipse([5, 3, 17, 15], fill=(165, 160, 194, 255))
        return ImageTk.PhotoImage(img)

    def _create_gradient_btn(self, w: int, h: int, top_col, bot_col, border_col, border_width=2) -> ImageTk.PhotoImage:
        grad_1d = Image.new("RGBA", (1, h))
        for y in range(h):
            r = int(top_col[0] + (bot_col[0] - top_col[0]) * (y / h))
            g = int(top_col[1] + (bot_col[1] - top_col[1]) * (y / h))
            b = int(top_col[2] + (bot_col[2] - top_col[2]) * (y / h))
            grad_1d.putpixel((0, y), (r, g, b, 255))
        grad = grad_1d.resize((w, h), Image.Resampling.BILINEAR)
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=255)
        btn = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        btn.paste(grad, (0, 0), mask)
        ImageDraw.Draw(btn).rounded_rectangle([0, 0, w - 1, h - 1], radius=10, outline=border_col, width=border_width)
        return ImageTk.PhotoImage(btn)

    def _build_bg_photo(self, art_key: str) -> ImageTk.PhotoImage:
        art_path = ASSETS_DIR / f"{art_key}.png"
        if art_path.is_file():
            base = Image.open(art_path).convert("RGBA")
            new_w = int(base.height * (WIDTH / HEIGHT))
            # Shift crop rightwards for pic0 so Investigation Team & logo sit cleanly on the right
            left = int((base.width - new_w) * (0.72 if art_key == "pic0" else 0.10))
            base = base.crop((left, 0, left + new_w, base.height)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        else:
            base = Image.new("RGBA", (WIDTH, HEIGHT), (14, 10, 28, 255))

        # Left frosted panel blur matching Basara 4 Sumeragi launcher
        blurred = base.filter(ImageFilter.GaussianBlur(radius=9))
        grad_blur = Image.new("L", (WIDTH, 1))
        d_b = ImageDraw.Draw(grad_blur)
        for x in range(WIDTH):
            val = 255 if x <= 480 else int(255 * (1.0 - (x - 480) / 110.0)) if x <= 590 else 0
            d_b.point((x, 0), fill=val)
        comp = Image.composite(blurred, base, grad_blur.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR))

        # Smooth cosine dark gradient from left controls to transparent artwork on right
        grad_x = Image.new("L", (WIDTH, 1))
        d_x = ImageDraw.Draw(grad_x)
        for x in range(WIDTH):
            if x <= 485:
                val = 242
            elif x <= 670:
                ratio = (x - 485) / 185.0
                val = int(242 * 0.5 * (1.0 + math.cos(ratio * math.pi)))
            else:
                val = 0
            d_x.point((x, 0), fill=val)
        mask_x = grad_x.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)

        grad_y = Image.new("L", (1, HEIGHT))
        d_y = ImageDraw.Draw(grad_y)
        v_start = int(HEIGHT * 0.78)
        for y in range(HEIGHT):
            val = int(205 * ((y - v_start) / float(HEIGHT - v_start))) if y >= v_start else int(75 * (1.0 - y / 45.0)) if y <= 45 else 0
            d_y.point((0, y), fill=val)
        mask_y = grad_y.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)

        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (11, 8, 24, 0))
        overlay.putalpha(ImageChops.lighter(mask_x, mask_y))
        return ImageTk.PhotoImage(Image.alpha_composite(comp, overlay))

    def _generate_textures(self):
        self._bg_cache = {k: self._build_bg_photo(k) for k in ("pic0", "pic1") if (ASSETS_DIR / f"{k}.png").is_file()}
        if not self._bg_cache:
            self._bg_cache["pic0"] = self._build_bg_photo("pic0")

        icon_p = ASSETS_DIR / "icon0.png"
        self.photo_icon0 = None
        if icon_p.is_file():
            ic = Image.open(icon_p).convert("RGBA").resize((52, 52), Image.Resampling.LANCZOS)
            mask = Image.new("L", (52, 52), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, 51, 51], radius=8, fill=255)
            rnd = Image.new("RGBA", (52, 52), (0, 0, 0, 0))
            rnd.paste(ic, (0, 0), mask)
            ImageDraw.Draw(rnd).rounded_rectangle([0, 0, 51, 51], radius=8, outline=(255, 226, 40, 220), width=1)
            self.photo_icon0 = ImageTk.PhotoImage(rnd)

        self.pills_res = self._create_pill_set(98, 26)
        self.pills_fps = self._create_pill_set(68, 26)
        self.pills_up = self._create_pill_set(86, 26)
        self.pills_aspect = self._create_pill_set(64, 26)
        self.pills_prio = self._create_pill_set(62, 24)

        self.btn_tool_norm = self._create_pill_tex(106, 26, (30, 27, 50, 230), (245, 208, 0, 200))
        self.btn_tool_hov = self._create_pill_tex(106, 26, (48, 43, 80, 245), (255, 230, 0, 255))
        self.btn_auto_norm = self._create_pill_tex(128, 26, (30, 27, 50, 230), (245, 208, 0, 200))
        self.btn_auto_hov = self._create_pill_tex(128, 26, (48, 43, 80, 245), (255, 230, 0, 255))
        self.btn_lang_norm = self._create_pill_tex(144, 28, (24, 21, 42, 235), (245, 208, 0, 210), radius=7)
        self.btn_lang_hov = self._create_pill_tex(144, 28, (44, 38, 76, 245), (255, 230, 0, 255), radius=7)

        self.sw_on = self._create_switch_tex(True)
        self.sw_off = self._create_switch_tex(False)

        self.btn_play_norm = self._create_gradient_btn(260, 50, (216, 27, 96), (136, 14, 79), (255, 230, 0), 2)
        self.btn_play_hov = self._create_gradient_btn(260, 50, (244, 42, 118), (168, 20, 96), (255, 248, 120), 2)
        self.btn_play_dis = self._create_gradient_btn(260, 50, (36, 33, 56), (24, 22, 38), (72, 68, 100), 1)

    def _make_pill_group(self, options, x0: int, y: int, step: int, pill_set, on_click):
        items = []
        _, inact, _ = pill_set
        w_half = inact.width() // 2
        h_half = inact.height() // 2
        for i, (label, val) in enumerate(options):
            x = x0 + i * step
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + w_half, y + h_half, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)
            tag = f"pill_{id(items)}_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))
            self.canvas.tag_bind(tag, "<Enter>", lambda e, it=items, idx=i, ps=pill_set: self._hover_pill(it, idx, ps, True))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, it=items, idx=i, ps=pill_set: self._hover_pill(it, idx, ps, False))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: on_click(v))
            items.append([img_id, txt_id, val, False])
        return items

    def _hover_pill(self, items, idx: int, pill_set, enter: bool):
        self.canvas.config(cursor="hand2" if enter else "arrow")
        img_id, txt_id, _, is_active = items[idx]
        if is_active:
            return
        act, inact, hov = pill_set
        self.canvas.itemconfig(img_id, image=hov if enter else inact)
        self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE if enter else COLOR_TEXT_MUTED)

    def _paint_pill_group(self, items, current_val: str, pill_set):
        act, inact, _ = pill_set
        for item in items:
            active = item[2] == current_val
            item[3] = active
            self.canvas.itemconfig(item[0], image=act if active else inact)
            self.canvas.itemconfig(item[1], fill=COLOR_TEXT_WHITE if active else COLOR_TEXT_MUTED)

    def _make_switch(self, x: int, y: int, title_key: str, sub_key: str, on_toggle):
        sw_id = self.canvas.create_image(x, y, image=self.sw_off, anchor="nw")
        t_id = self.canvas.create_text(x + 48, y - 1, text=self.tr(title_key), font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        s_id = self.canvas.create_text(x + 48, y + 15, text=self.tr(sub_key), font=(FONT_FAMILY, 8), fill=COLOR_TEXT_SUB, anchor="nw")
        tag = f"sw_{id(sw_id)}"
        for it in (sw_id, t_id, s_id):
            self.canvas.itemconfig(it, tags=(tag,))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag, "<Button-1>", lambda e: on_toggle())
        return sw_id, t_id, s_id, title_key, sub_key

    def _make_action_pill(self, x: int, y: int, norm, hov, text: str, color: str, cmd):
        img_id = self.canvas.create_image(x, y, image=norm, anchor="nw")
        txt_id = self.canvas.create_text(x + norm.width() // 2, y + norm.height() // 2, text=text, font=(FONT_FAMILY, 8, "bold"), fill=color)
        tag = f"act_{id(img_id)}"
        for it in (img_id, txt_id):
            self.canvas.itemconfig(it, tags=(tag,))
        self.canvas.tag_bind(tag, "<Enter>", lambda e: (self.canvas.config(cursor="hand2"), self.canvas.itemconfig(img_id, image=hov)))
        self.canvas.tag_bind(tag, "<Leave>", lambda e: (self.canvas.config(cursor="arrow"), self.canvas.itemconfig(img_id, image=norm)))
        self.canvas.tag_bind(tag, "<Button-1>", lambda e: cmd())
        return img_id, txt_id

    def _build_canvas(self):
        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT, highlightthickness=0, bg=COLOR_BG_DARK)
        self.canvas.pack(fill="both", expand=True)

        bg_photo = self._bg_cache.get(self.artwork_key, next(iter(self._bg_cache.values())))
        self.bg_item = self.canvas.create_image(0, 0, image=bg_photo, anchor="nw")

        # Header + Brand
        tx = 36
        if self.photo_icon0:
            self.canvas.create_image(36, 24, image=self.photo_icon0, anchor="nw")
            tx = 100

        self.canvas.create_text(tx, 24, text="VULKAN 1.3 NATIVE PORT • CUSA12112", font=(FONT_FAMILY, 8, "bold"), fill=COLOR_GOLD, anchor="nw")
        self.canvas.create_text(tx + 1, 41, text="PERSONA 4", font=(FONT_FAMILY, 19, "bold"), fill="#000000", anchor="nw")
        self.canvas.create_text(tx, 40, text="PERSONA 4", font=(FONT_FAMILY, 19, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        self.canvas.create_text(tx, 70, text="D A N C I N G   A L L   N I G H T", font=(FONT_FAMILY, 10, "bold"), fill=COLOR_GOLD_BRIGHT, anchor="nw")
        self.lbl_sub = self.canvas.create_text(tx, 89, text=self.tr("subtitle"), font=(FONT_FAMILY, 8), fill=COLOR_TEXT_SUB, anchor="nw")

        # Language Selector (Top-Right)
        self.lang_img, self.lang_txt = self._make_action_pill(WIDTH - 36 - 144, 24, self.btn_lang_norm, self.btn_lang_hov, self.tr("lang_badge"), COLOR_GOLD_BRIGHT, self._toggle_lang)

        self.canvas.create_line(36, 112, 510, 112, fill="#2A2442", width=1)

        # 1. Display Resolution
        self.lbl_sec_res = self.canvas.create_text(36, 122, text=self.tr("sec_res"), font=(FONT_FAMILY, 9, "bold"), fill="#DFDAEE", anchor="nw")
        self.res_items = self._make_pill_group(
            [("1280×720", "1280x720"), ("1920×1080", "1920x1080"), ("2560×1440", "2560x1440"), ("3840×2160", "3840x2160")],
            36, 142, 106, self.pills_res, self._select_res,
        )

        # 2. Target FPS + Auto-Optimize
        self.lbl_sec_fps = self.canvas.create_text(36, 180, text=self.tr("sec_fps"), font=(FONT_FAMILY, 9, "bold"), fill="#DFDAEE", anchor="nw")
        self.fps_items = self._make_pill_group(
            [("60 FPS", "60"), ("90 FPS", "90"), ("120 FPS", "120"), ("144 FPS", "144"), ("Max", "0")],
            36, 200, 74, self.pills_fps, self._select_fps,
        )
        self.auto_img, self.auto_txt = self._make_action_pill(414, 200, self.btn_auto_norm, self.btn_auto_hov, self.tr("btn_auto"), COLOR_GOLD_BRIGHT, self._auto_optimize)

        # 3. Upscaler Mode
        self.lbl_sec_up = self.canvas.create_text(36, 238, text=self.tr("sec_upscaler"), font=(FONT_FAMILY, 9, "bold"), fill="#DFDAEE", anchor="nw")
        self.up_items = self._make_pill_group(
            [("Native", "off"), ("FSR 1", "fsr1"), ("FSR 3.1", "fsr3"), ("DLSS", "dlss")],
            36, 258, 94, self.pills_up, self._select_upscaler,
        )

        # 4. Aspect Ratio & Sharpness Slider
        self.lbl_sec_aspect = self.canvas.create_text(36, 294, text=self.tr("sec_aspect"), font=(FONT_FAMILY, 9, "bold"), fill="#DFDAEE", anchor="nw")
        self.aspect_items = self._make_pill_group([("16:9", "16:9"), ("21:9", "21:9"), ("32:9", "32:9")], 36, 314, 70, self.pills_aspect, self._select_aspect)

        self.lbl_sharp = self.canvas.create_text(276, 294, text=self.tr("sharpness", val=self.sharp_val), font=(FONT_FAMILY, 9, "bold"), fill="#DFDAEE", anchor="nw")
        hx = 276 + int((self.sharp_val / 100.0) * 200)
        self.canvas.create_line(276, 327, 476, 327, fill="#221D3A", width=6, capstyle="round", tags=("slider_sharp",))
        self.slider_fill = self.canvas.create_line(276, 327, hx, 327, fill=COLOR_MAGENTA, width=6, capstyle="round", tags=("slider_sharp",))
        self.slider_knob = self.canvas.create_oval(hx - 8, 327 - 8, hx + 8, 327 + 8, fill=COLOR_GOLD_BRIGHT, outline="#FFFFFF", width=1.5, tags=("slider_sharp",))
        self.canvas.create_rectangle(266, 312, 486, 342, fill="", outline="", tags=("slider_sharp",))
        self.canvas.tag_bind("slider_sharp", "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind("slider_sharp", "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind("slider_sharp", "<Button-1>", self._on_slider)
        self.canvas.tag_bind("slider_sharp", "<B1-Motion>", self._on_slider)

        # 5. Engine Preferences (2x3 switches)
        self.lbl_sec_prefs = self.canvas.create_text(36, 354, text=self.tr("sec_prefs"), font=(FONT_FAMILY, 9, "bold"), fill="#DFDAEE", anchor="nw")
        self.switches = [
            self._make_switch(36, 376, "t_full_t", "t_full_s", lambda: self._toggle("full_val")),
            self._make_switch(276, 376, "t_sharpen_t", "t_sharpen_s", lambda: self._toggle("sharpen_val")),
            self._make_switch(36, 416, "t_async_t", "t_async_s", lambda: self._toggle("async_val")),
            self._make_switch(276, 416, "t_fps_t", "t_fps_s", lambda: self._toggle("show_fps_val")),
            self._make_switch(36, 456, "t_fg_t", "t_fg_s", lambda: self._toggle("fg_val")),
            self._make_switch(276, 456, "t_msaa_t", "t_msaa_s", lambda: self._toggle("msaa_val")),
        ]

        # 6. Process Priority + Artwork Toggle
        self.lbl_prio = self.canvas.create_text(36, 511, text=self.tr("lbl_prio"), font=(FONT_FAMILY, 9, "bold"), fill=COLOR_GOLD_BRIGHT, anchor="w")
        self.prio_items = self._make_pill_group(
            [(self.tr("prio_norm"), "normal"), (self.tr("prio_above"), "above_normal"), (self.tr("prio_high"), "high")],
            126, 499, 68, self.pills_prio, self._select_prio,
        )
        self.art_img, self.art_txt = self._make_action_pill(348, 498, self.btn_auto_norm, self.btn_auto_hov, self._art_btn_label(), COLOR_GOLD_BRIGHT, self._toggle_artwork)

        # 7. Utility Toolbar Row
        self.pad_img, self.pad_txt = self._make_action_pill(36, 534, self.btn_tool_norm, self.btn_tool_hov, self.tr("btn_pad"), COLOR_GOLD, self._open_controls_help)
        self.save_img, self.save_txt = self._make_action_pill(148, 534, self.btn_tool_norm, self.btn_tool_hov, self.tr("btn_save"), COLOR_GOLD, self._open_saves)
        self.log_img, self.log_txt = self._make_action_pill(260, 534, self.btn_tool_norm, self.btn_tool_hov, self.tr("btn_log"), COLOR_GOLD, self._open_log_window)
        self.dir_img, self.dir_txt = self._make_action_pill(372, 534, self.btn_auto_norm, self.btn_auto_hov, self.tr("btn_dir"), COLOR_GOLD_BRIGHT, self._browse_app0)
        self.shot_img, self.shot_txt = self._make_action_pill(WIDTH - 36 - 128, 534, self.btn_auto_norm, self.btn_auto_hov, self.tr("btn_shot"), COLOR_GOLD_BRIGHT, self._on_screenshot)
        shot_tags = self.canvas.gettags(self.shot_img)
        if shot_tags:
            self.canvas.tag_bind(shot_tags[0], "<Button-3>", lambda e: self._open_screenshots_folder())

        # 8. Footer Status & Giant PLAY Button
        self.canvas.create_line(36, 576, WIDTH - 36, 576, fill="#2A2442", width=1)
        self.footer_status = self.canvas.create_text(38, 616, text="", font=(FONT_FAMILY, 8, "bold"), fill="#B9B3D6", anchor="w")

        px, py = WIDTH - 36 - 260, 591
        self.play_img = self.canvas.create_image(px, py, image=self.btn_play_norm, anchor="nw")
        self.play_txt = self.canvas.create_text(px + 130, py + 25, text=self.tr("play"), font=(FONT_FAMILY, 13, "bold"), fill=COLOR_TEXT_WHITE)
        for it in (self.play_img, self.play_txt):
            self.canvas.itemconfig(it, tags=("btn_play",))
        self.canvas.tag_bind("btn_play", "<Enter>", lambda e: self._hover_play(True))
        self.canvas.tag_bind("btn_play", "<Leave>", lambda e: self._hover_play(False))
        self.canvas.tag_bind("btn_play", "<Button-1>", lambda e: self._on_play())

    def _art_btn_label(self) -> str:
        return self.tr("btn_art_0") if self.artwork_key == "pic0" else self.tr("btn_art_1")

    def refresh_controls(self):
        self._paint_pill_group(self.res_items, self.res_val, self.pills_res)
        self._paint_pill_group(self.fps_items, self.fps_val, self.pills_fps)
        self._paint_pill_group(self.up_items, self.upscaler_val, self.pills_up)
        self._paint_pill_group(self.aspect_items, self.aspect_val, self.pills_aspect)
        self._paint_pill_group(self.prio_items, self.prio_val, self.pills_prio)

        states = (self.full_val, self.sharpen_val, self.async_val, self.show_fps_val, self.fg_val, self.msaa_val)
        for sw, active in zip(self.switches, states):
            self.canvas.itemconfig(sw[0], image=self.sw_on if active else self.sw_off)

        has_exe = resolve_engine_exe().is_file()
        has_dump = not validate_game_dir(self.app0_dir)
        has_boot = boot_files_ready()
        has_save = (USER_DIR / "savedata" / "1" / "CUSA12112" / "SYSTEM" / "SYSTEM.DAT").is_file()

        ready = has_exe and has_dump
        running = self.proc is not None and self.proc.poll() is None
        dump_s = "OK" if has_dump else "NONE"
        boot_s = "OK" if has_boot else "AUTO"
        save_s = "OK" if has_save else "NEW"
        vk_s = "OK" if self.vulkan_ok else "NO DLL"
        toast = getattr(self, "_toast_msg", None)
        self.canvas.itemconfig(
            self.footer_status,
            text=toast or f"GPU: {self.gpu_name}  |  Dump: {dump_s}  |  Boot: {boot_s}  |  Save: {save_s}  |  Vulkan: {vk_s}",
            fill=COLOR_GOLD_BRIGHT if toast else (COLOR_CYAN if ready else "#FF4D88"),
        )
        if self.preparing:
            self.canvas.itemconfig(self.play_img, image=self.btn_play_dis)
            self.canvas.itemconfig(self.play_txt, text=self.tr("preparing"), fill=COLOR_GOLD_BRIGHT)
        elif running:
            self.canvas.itemconfig(self.play_img, image=self.btn_play_dis)
            self.canvas.itemconfig(self.play_txt, text=self.tr("running"), fill=COLOR_TEXT_MUTED)
        elif ready:
            self.canvas.itemconfig(self.play_img, image=self.btn_play_norm)
            self.canvas.itemconfig(self.play_txt, text=self.tr("play"), fill=COLOR_TEXT_WHITE)
        else:
            self.canvas.itemconfig(self.play_img, image=self.btn_play_norm)
            self.canvas.itemconfig(self.play_txt, text=self.tr("missing"), fill="#FFE600")

    def _apply_language(self):
        self.canvas.itemconfig(self.lang_txt, text=self.tr("lang_badge"))
        self.canvas.itemconfig(self.lbl_sub, text=self.tr("subtitle"))
        self.canvas.itemconfig(self.lbl_sec_res, text=self.tr("sec_res"))
        self.canvas.itemconfig(self.lbl_sec_fps, text=self.tr("sec_fps"))
        self.canvas.itemconfig(self.lbl_sec_up, text=self.tr("sec_upscaler"))
        self.canvas.itemconfig(self.lbl_sec_aspect, text=self.tr("sec_aspect"))
        self.canvas.itemconfig(self.lbl_sec_prefs, text=self.tr("sec_prefs"))
        self.canvas.itemconfig(self.lbl_sharp, text=self.tr("sharpness", val=self.sharp_val))
        self.canvas.itemconfig(self.lbl_prio, text=self.tr("lbl_prio"))
        self.canvas.itemconfig(self.auto_txt, text=self.tr("btn_auto"))
        self.canvas.itemconfig(self.art_txt, text=self._art_btn_label())
        self.canvas.itemconfig(self.pad_txt, text=self.tr("btn_pad"))
        self.canvas.itemconfig(self.save_txt, text=self.tr("btn_save"))
        self.canvas.itemconfig(self.log_txt, text=self.tr("btn_log"))
        self.canvas.itemconfig(self.dir_txt, text=self.tr("btn_dir"))
        self.canvas.itemconfig(self.shot_txt, text=self.tr("btn_shot"))
        for _, t_id, s_id, tk_key, sk_key in self.switches:
            self.canvas.itemconfig(t_id, text=self.tr(tk_key))
            self.canvas.itemconfig(s_id, text=self.tr(sk_key))
        for item, key in zip(self.prio_items, ("prio_norm", "prio_above", "prio_high")):
            self.canvas.itemconfig(item[1], text=self.tr(key))
        self.refresh_controls()

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "id" else "id"
        self._apply_language()
        self._sync_ini()

    def _toggle_artwork(self):
        self.artwork_key = "pic1" if self.artwork_key == "pic0" else "pic0"
        if self.artwork_key in self._bg_cache:
            self.canvas.itemconfig(self.bg_item, image=self._bg_cache[self.artwork_key])
        self.canvas.itemconfig(self.art_txt, text=self._art_btn_label())
        self._sync_ini()

    def _select_res(self, val: str):
        self.res_val = val
        self._sync_ini()
        self.refresh_controls()

    def _select_fps(self, val: str):
        self.fps_val = val
        self._sync_ini()
        self.refresh_controls()

    def _select_upscaler(self, val: str):
        self.upscaler_val = val
        self._sync_ini()
        self.refresh_controls()

    def _select_aspect(self, val: str):
        self.aspect_val = val
        self._sync_ini()
        self.refresh_controls()

    def _select_prio(self, val: str):
        self.prio_val = val
        self._sync_ini()
        self.refresh_controls()

    def _toggle(self, attr: str):
        setattr(self, attr, not getattr(self, attr))
        self._sync_ini()
        self.refresh_controls()

    def _on_slider(self, event):
        clamped = max(276, min(476, event.x))
        self.sharp_val = int(round(((clamped - 276) / 200.0) * 100))
        self.canvas.coords(self.slider_fill, 276, 327, clamped, 327)
        self.canvas.coords(self.slider_knob, clamped - 8, 327 - 8, clamped + 8, 327 + 8)
        self.canvas.itemconfig(self.lbl_sharp, text=self.tr("sharpness", val=self.sharp_val))
        self._sync_ini()

    def _auto_optimize(self):
        self.res_val = "1920x1080"
        self.fps_val = "60"
        self.upscaler_val = "fsr1"
        self.sharpen_val = True
        self.sharp_val = 35
        self.async_val = True
        self.fg_val = False
        self.msaa_val = False
        self.prio_val = "high"
        hx = 276 + int((self.sharp_val / 100.0) * 200)
        self.canvas.coords(self.slider_fill, 276, 327, hx, 327)
        self.canvas.coords(self.slider_knob, hx - 8, 327 - 8, hx + 8, 327 + 8)
        self.canvas.itemconfig(self.lbl_sharp, text=self.tr("sharpness", val=self.sharp_val))
        self._sync_ini()
        self.refresh_controls()
        messagebox.showinfo("Auto-Optimize", "Optimal settings applied for Rhythm Sync (1080p • 60 FPS • FSR 1 • Async Shader).")

    def _open_controls_help(self):
        messagebox.showinfo(
            "Persona 4: Dancing All Night Controls",
            "Gamepad (XInput / DualShock):\n"
            "  • Auto-detected natively on Port 1\n\n"
            "Keyboard Mapping:\n"
            "  • D-Pad (Notes Left):  I (Up)  J (Left)  K (Down)  L (Right)\n"
            "  • Face (Notes Right): Q (Triangle)  LShift (Circle)  Space (Cross)  E (Square)\n"
            "  • Fever / Scratch: WASD (L-Stick)  &  Arrow Keys (R-Stick)\n"
            "  • Options / Pause: Enter\n"
            "  • Touchpad: Tab (Left)  /  Backspace (Right)\n"
            "  • Screenshot: F12 (In-Game) or Launcher Screenshot button\n\n"
            "In-Game Graphics & Pad Menu: Press Insert or L3 + R3",
        )

    def _open_saves(self):
        save_dir = USER_DIR / "savedata" / "1" / "CUSA12112"
        save_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(save_dir))

    def _show_toast(self, msg: str, duration_ms: int = 3500):
        self._toast_msg = msg
        self._toast_token = getattr(self, "_toast_token", 0) + 1
        tok = self._toast_token
        self.refresh_controls()

        def clear():
            if getattr(self, "_toast_token", 0) == tok:
                self._toast_msg = None
                self.refresh_controls()

        self.after(duration_ms, clear)

    def _open_screenshots_folder(self):
        shots_dir = USER_DIR / "screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(shots_dir))
        self._show_toast(self.tr("shot_folder"))

    def _on_screenshot(self):
        shots_dir = USER_DIR / "screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        running = self.proc is not None and self.proc.poll() is None
        if not running:
            self._open_screenshots_folder()
            return
        before = {p.name for p in shots_dir.glob("*.png")}
        USER_DIR.mkdir(parents=True, exist_ok=True)
        (USER_DIR / "screenshot.trigger").write_text("1", encoding="utf-8")
        self._wait_screenshot(shots_dir, before, 0)

    def _wait_screenshot(self, shots_dir: Path, before: set[str], attempt: int):
        new_files = sorted(p for p in shots_dir.glob("*.png") if p.name not in before)
        if new_files:
            newest = new_files[-1].name
            self._append_log(f"[SCREENSHOT] Saved: {shots_dir / newest}\n")
            self._show_toast(self.tr("shot_saved", name=newest))
            return
        if attempt < 20:
            self.after(120, lambda: self._wait_screenshot(shots_dir, before, attempt + 1))

    def _browse_app0(self):
        init = str(self.app0_dir) if self.app0_dir.is_dir() else str(BASE_DIR)
        chosen = filedialog.askdirectory(title="Pilih Folder Dump PS4 Persona 4 (CUSA12112 / uroot)", initialdir=init)
        if not chosen:
            return False
        p = unwrap_game_dir(Path(chosen))
        missing = validate_game_dir(p)
        if missing:
            messagebox.showwarning(
                "Dump PS4 Tidak Lengkap",
                "Folder tidak valid. File berikut wajib ada di dalam folder dump PS4:\n\n• "
                + "\n• ".join(missing)
                + "\n\nPastikan memilih folder CUSA12112 atau app0\\uroot hasil dump lengkap.",
            )
            return False
        self.app0_dir = p
        sync_assets_from_dump(p)
        self._sync_ini()
        self.refresh_controls()
        if not boot_files_ready():
            self._start_prepare_only()
        return True

    def _start_prepare_only(self):
        if self.preparing:
            return
        self.preparing = True
        self.refresh_controls()

        def worker():
            try:
                run_auto_prepare(self.app0_dir, self.log_queue.put)
                self.log_queue.put("__REFRESH__")
            except Exception as exc:
                self.log_queue.put(f"__PREP_ERR__:{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _open_log_window(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.lift()
            return
        win = tk.Toplevel(self)
        win.title("Persona 4: Dancing All Night — Runtime Log")
        win.geometry("860x480")
        win.configure(bg=COLOR_BG_DARK)
        txt = scrolledtext.ScrolledText(win, bg="#080612", fg="#EAE6FA", insertbackground=COLOR_GOLD_BRIGHT, font=("Consolas", 9), relief="flat")
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        if self.log_buffer:
            txt.insert("end", "".join(self.log_buffer[-1500:]))
            txt.see("end")
        elif LOG_PATH.is_file():
            txt.insert("end", LOG_PATH.read_text(encoding="utf-8", errors="replace")[-12000:])
            txt.see("end")
        self.log_window = win
        self.log_text = txt

    def _append_log(self, line: str):
        self.log_buffer.append(line)
        if len(self.log_buffer) > 3000:
            self.log_buffer = self.log_buffer[-2000:]
        if self.log_text and self.log_window and self.log_window.winfo_exists():
            self.log_text.insert("end", line)
            self.log_text.see("end")

    def _poll_logs(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if item == "__REFRESH__":
                    self.preparing = False
                    self.refresh_controls()
                elif item.startswith("__PREP_ERR__:"):
                    self.preparing = False
                    self.refresh_controls()
                    messagebox.showerror("Setup Failed", item.split(":", 1)[1])
                elif item.startswith("__EXIT__:"):
                    self._on_game_exit(int(item.split(":", 1)[1]))
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.after(100, self._poll_logs)

    def _hover_play(self, enter: bool):
        if self.preparing or (self.proc and self.proc.poll() is None):
            return
        self.canvas.config(cursor="hand2" if enter else "arrow")
        self.canvas.itemconfig(self.play_img, image=self.btn_play_hov if enter else self.btn_play_norm)

    def _on_play(self):
        if self.preparing or (self.proc and self.proc.poll() is None):
            return
        engine_exe = resolve_engine_exe()
        if not engine_exe.is_file():
            messagebox.showerror("Missing Engine", f"Engine executable not found:\n{engine_exe}")
            return
        if validate_game_dir(self.app0_dir):
            if not self._browse_app0():
                return
            if validate_game_dir(self.app0_dir):
                return
        self._sync_ini()
        self.log_buffer.clear()
        if self.log_text and self.log_window and self.log_window.winfo_exists():
            self.log_text.delete("1.0", "end")
        if not boot_files_ready():
            self.preparing = True
        threading.Thread(target=self._run_game_loop, daemon=True).start()
        self.refresh_controls()

    def _run_game_loop(self):
        if not boot_files_ready():
            try:
                run_auto_prepare(self.app0_dir, self.log_queue.put)
            except Exception as exc:
                self.log_queue.put(f"__PREP_ERR__:{exc}")
                return
            self.log_queue.put("__REFRESH__")

        env = os.environ.copy()
        env["PATH"] = f"{BASE_DIR};{env.get('PATH', '')}"
        env["BB_CONFIG"] = str(INI_PATH)
        env["BB_DATA_DIR"] = str(BASE_DIR)
        env["BB_GPU_USER_DIR"] = str(USER_DIR)
        env["BB_GUEST_IN_PLACE"] = "0"
        env["BB_UFFD"] = "0"
        env["BB_COPY_GPU_BUFFERS"] = "1"
        env["BB_GPU_WRITE_TWINS"] = "1"
        env["BB_GPU_WRITE_TWINS_MAX"] = "65536"
        env["BB_PREUPLOAD"] = "1"
        env["BB_VBLANK_HZ"] = "0" if self.fps_val == "0" else self.fps_val
        env["BB_FPS_LIMIT"] = self.fps_val
        env["BB_ASYNC_PIPELINES"] = "1" if self.async_val else "0"
        env["BB_PRIORITY"] = self.prio_val
        env["BB_NEO"] = "0"

        engine_exe = resolve_engine_exe()
        cmd = [
            str(engine_exe),
            str(OUT_DIR / "boot-linked.bin"),
            "--import-names", str(OUT_DIR / "import_names.txt"),
            "--content-profile", str(OUT_DIR / "content.bin"),
            "--patches", str(OUT_DIR / "patches.bin"),
            "--app0", str(self.app0_dir),
            "--user", str(USER_DIR),
            "--timeout", "0",
        ]

        rc = 0
        while True:
            self.proc = subprocess.Popen(
                cmd, cwd=str(BASE_DIR), env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", creationflags=NO_WINDOW,
            )
            with LOG_PATH.open("w", encoding="utf-8", errors="replace") as log_f:
                assert self.proc.stdout is not None
                for line in self.proc.stdout:
                    log_f.write(line)
                    log_f.flush()
                    self.log_queue.put(line)
            rc = self.proc.wait()
            if rc != 75:
                break
            self.log_queue.put("\n--- Restarting after settings change (code 75) ---\n")
        self.log_queue.put(f"__EXIT__:{rc}")

    def _on_game_exit(self, rc: int):
        self.proc = None
        self.refresh_controls()
        if rc != 0:
            self._open_log_window()


def main():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Persona4Dancing.PC.Launcher")
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = P4BasaraStyleLauncher()
    app.mainloop()


if __name__ == "__main__":
    main()
