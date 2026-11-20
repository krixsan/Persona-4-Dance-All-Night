#!/usr/bin/env python3
"""Build Persona 4: Dancing All Night PC launcher and optional portable release folder."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_DIR = ROOT / "launcher"
LAUNCHER_SCRIPT = LAUNCHER_DIR / "P4DAN_Launcher.pyw"
ASSETS_DIR = LAUNCHER_DIR / "assets"
ICON_PATH = ROOT / "packaging" / "windows" / "icons" / "p4dan.ico"
SCRIPTS_SRC = ROOT / "scripts"
TOOLS_SRC = ROOT / "tools"

RUNTIME_SCRIPTS = (
    SCRIPTS_SRC / "prepare.py",
    SCRIPTS_SRC / "link_libc.py",
    SCRIPTS_SRC / "link_modules.py",
    SCRIPTS_SRC / "content_profile.py",
    SCRIPTS_SRC / "patches.py",
    SCRIPTS_SRC / "game_check.py",
    TOOLS_SRC / "gen_import_names.py",
)

EXE_NAME = "Persona 4 Dancing All Night"


def find_game_dir(cli_dir: str | None) -> Path | None:
    """Locate an extracted PS4 CUSA12112 uroot/app0 folder for optional local icon/art extraction."""
    raw_candidates: list[Path] = []
    if cli_dir:
        raw_candidates.append(Path(cli_dir))
    raw_candidates.extend([
        ROOT / "game_data",
        ROOT / "CUSA12112",
        ROOT / "00_GAME_DUMP" / "CUSA12112",
        ROOT.parent / "00_GAME_DUMP" / "CUSA12112",
    ])
    for base in raw_candidates:
        for cand in (base, base / "uroot", base / "app0" / "uroot", base / "app0"):
            if (cand / "sce_sys" / "icon0.png").is_file() and (cand / "eboot.bin").is_file():
                return cand
    return None


def write_hybrid_ico(src_png: Path, dst_ico: Path) -> None:
    """Create a Windows hybrid ICO (DIB BMP for <=64px, PNG for 128/256px)."""
    from PIL import Image

    img = Image.open(src_png).convert("RGBA")
    frames: list[tuple[int, bytes]] = []
    for size, fmt in ((16, "bmp"), (24, "bmp"), (32, "bmp"), (48, "bmp"), (64, "bmp"), (128, "png"), (256, "png")):
        bio = io.BytesIO()
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(bio, format="ICO", sizes=[(size, size)], bitmap_format=fmt)
        raw = bio.getvalue()
        offset = struct.unpack_from("<I", raw, 18)[0]
        length = struct.unpack_from("<I", raw, 14)[0]
        frames.append((size, raw[offset : offset + length]))

    dst_ico.parent.mkdir(parents=True, exist_ok=True)
    header = struct.pack("<HHH", 0, 1, len(frames))
    entries = bytearray()
    payload = bytearray()
    cur_offset = 6 + 16 * len(frames)
    for size, data in frames:
        dim = 0 if size >= 256 else size
        entries.extend(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), cur_offset))
        payload.extend(data)
        cur_offset += len(data)
    dst_ico.write_bytes(header + bytes(entries) + bytes(payload))


def prepare_local_assets(game_dir: Path | None) -> None:
    """Extract PS4 artwork and build hybrid p4dan.ico locally (gitignored)."""
    if game_dir is None:
        return
    sce_sys = game_dir / "sce_sys"
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("icon0.png", "pic0.png", "pic1.png"):
        src = sce_sys / name
        if src.is_file():
            shutil.copy2(src, ASSETS_DIR / name)

    icon0 = ASSETS_DIR / "icon0.png"
    if icon0.is_file():
        write_hybrid_ico(icon0, ICON_PATH)
        shutil.copy2(ICON_PATH, ASSETS_DIR / "p4dan.ico")
        print(f"[ICON] Built hybrid icon -> {ICON_PATH}")


def _find_msys2_root() -> Path:
    env_root = os.environ.get("MSYS2_ROOT")
    for cand in ([Path(env_root)] if env_root else []) + [Path(r"F:\msys64"), Path(r"C:\msys64")]:
        if (cand / "clang64" / "bin").is_dir():
            return cand
    raise FileNotFoundError("MSYS2 CLANG64 root not found (checked MSYS2_ROOT, F:\\msys64, C:\\msys64)")


def collect_msys2_dlls(exe_path: Path, target_dir: Path) -> int:
    """Copy non-system MSYS2 CLANG64 runtime DLLs required by sacredfire/p4dan_pc.exe."""
    msys_root = _find_msys2_root()
    clang_bin = msys_root / "clang64" / "bin"
    ldd_exe = msys_root / "usr" / "bin" / "ldd.exe"
    copied = 0

    if ldd_exe.is_file():
        env = os.environ.copy()
        env["PATH"] = f"{clang_bin};{msys_root / 'usr' / 'bin'};{env.get('PATH', '')}"
        out = subprocess.check_output([str(ldd_exe), str(exe_path)], text=True, errors="replace", env=env)
        for line in out.splitlines():
            if "=>" not in line:
                continue
            rhs = line.split("=>", 1)[1].strip().split(" (", 1)[0].strip()
            if rhs.startswith("/clang64/"):
                win_dll = msys_root / rhs.lstrip("/").replace("/", os.sep)
                if win_dll.is_file():
                    shutil.copy2(win_dll, target_dir / win_dll.name)
                    copied += 1
        return copied

    for dll in clang_bin.glob("*.dll"):
        shutil.copy2(dll, target_dir / dll.name)
        copied += 1
    return copied


def build_exe(output_dir: Path | None = None) -> Path:
    """Compile P4DAN_Launcher.pyw via PyInstaller into Persona 4 Dancing All Night.exe."""
    dist_dir = output_dir or (ROOT / "dist")
    build_tmp = ROOT / "build" / "launcher_pyi"
    stage_scripts = build_tmp / "scripts"
    if build_tmp.exists():
        shutil.rmtree(build_tmp, ignore_errors=True)
    stage_scripts.mkdir(parents=True, exist_ok=True)
    for src in RUNTIME_SCRIPTS:
        if src.is_file():
            shutil.copy2(src, stage_scripts / src.name)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        EXE_NAME,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_tmp / "work"),
        "--specpath",
        str(build_tmp),
        "--add-data",
        f"{stage_scripts};scripts",
        "--hidden-import",
        "PIL.Image",
        "--hidden-import",
        "PIL.ImageTk",
        "--hidden-import",
        "PIL.ImageDraw",
        "--hidden-import",
        "PIL.ImageFilter",
        "--hidden-import",
        "PIL.ImageChops",
    ]
    if ASSETS_DIR.is_dir() and any(ASSETS_DIR.iterdir()):
        cmd.extend(["--add-data", f"{ASSETS_DIR};assets"])
    if ICON_PATH.is_file():
        cmd.extend(["--icon", str(ICON_PATH)])
    cmd.append(str(LAUNCHER_SCRIPT))

    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        sys.exit(res.returncode)

    built_exe = dist_dir / f"{EXE_NAME}.exe"
    shutil.rmtree(build_tmp, ignore_errors=True)
    print(f"[LAUNCHER] Built -> {built_exe}")
    return built_exe


def package_portable(package_dir: Path, built_launcher: Path) -> None:
    """Assemble a clean portable PC release folder (without game dump binaries)."""
    package_dir.mkdir(parents=True, exist_ok=True)
    if built_launcher.parent.resolve() != package_dir.resolve():
        shutil.copy2(built_launcher, package_dir / built_launcher.name)

    engine_src = ROOT / "out" / "sacredfire.exe"
    if not engine_src.is_file():
        raise FileNotFoundError(f"Engine binary not found: {engine_src}. Run ./build.sh first.")
    engine_dst = package_dir / "p4dan_pc.exe"
    shutil.copy2(engine_src, engine_dst)

    dll_count = collect_msys2_dlls(engine_src, package_dir)
    pkg_scripts = package_dir / "scripts"
    pkg_scripts.mkdir(parents=True, exist_ok=True)
    for src in RUNTIME_SCRIPTS:
        if src.is_file():
            shutil.copy2(src, pkg_scripts / src.name)

    if ASSETS_DIR.is_dir() and any(ASSETS_DIR.iterdir()):
        pkg_assets = package_dir / "assets"
        pkg_assets.mkdir(parents=True, exist_ok=True)
        for item in ASSETS_DIR.iterdir():
            if item.is_file():
                shutil.copy2(item, pkg_assets / item.name)

    for extra in ("launch_game.bat", "INSTALL.md"):
        src = ROOT / extra
        if src.is_file():
            shutil.copy2(src, package_dir / extra)

    (package_dir / "out").mkdir(exist_ok=True)
    (package_dir / "user").mkdir(exist_ok=True)
    print(f"[PACKAGE] Portable build ready in {package_dir} ({dll_count} runtime DLLs copied)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Persona 4: Dancing All Night PC Launcher")
    parser.add_argument("--game-dir", default=None, help="Optional PS4 dump folder (to embed local icon/art)")
    parser.add_argument("--dist-dir", default=None, help="Output directory for launcher exe (default: dist/)")
    parser.add_argument("--package", default=None, help="Also assemble full portable release folder at path")
    parser.add_argument("--icon-only", action="store_true", help="Only extract icon/assets for CMake build")
    args = parser.parse_args()

    game_dir = find_game_dir(args.game_dir)
    if game_dir:
        print(f"[ASSETS] Using local dump at {game_dir}")
        prepare_local_assets(game_dir)
    elif ICON_PATH.is_file():
        print(f"[ICON] Using existing {ICON_PATH}")
    else:
        print("[ASSETS] No local PS4 dump found; building launcher without bundled game art/icon.")

    if args.icon_only:
        return

    out_dir = Path(args.package) if args.package else (Path(args.dist_dir) if args.dist_dir else None)
    built = build_exe(out_dir)
    if args.package:
        package_portable(Path(args.package), built)


if __name__ == "__main__":
    main()
