# Persona 4: Dancing All Night — Native PC Port (`CUSA12112`)

Native source-only PC port of **Persona 4: Dancing All Night** (`CUSA12112`, PS4) powered by static/runtime PS4 ELF execution, Vulkan graphics (with FSR 1, FSR 3.1, and DLSS support), SDL3 input/windowing, LibAtrac9 + FFmpeg audio/video decoding, and a custom standalone launcher.

> [!IMPORTANT]
> **Source-Only Repository:** No copyrighted PS4 game binaries (`eboot.bin`, `.cpk`, `.prx`, `.pkg`), icons, artwork (`icon0.png`, `pic0.png`, `pic1.png`), or decryption keys are included in this repository. You must supply your own legitimate PS4 dump of `CUSA12112`.

---

## Features & Current Status

- **Native Windows Engine (`p4dan_pc.exe` / `out/sacredfire.exe`):** Boots `CUSA12112` past PS4 system init, `CriMana` video decoding, `/savedata0`, and renders via Vulkan at **~60 FPS** with in-game live menu (`Insert` or `L3 + R3`).
- **Custom Standalone Launcher (`launcher/P4DAN_Launcher.pyw` -> `Persona 4 Dancing All Night.exe`):**
  - **First-Run Auto-Setup:** Automatically runs module linking (`libc.prx`, `libSceFios2.prx`), host import symbol generation, AppContent profile, and patch setup from your PS4 dump folder.
  - **Portable Drive Paths:** Uses relative paths anchored to the launcher directory (`launcher_dir` check) so moving the entire folder to another drive (e.g., `J:\`) continues working seamlessly.
  - **Graphics & Performance Controls:** Internal resolution (720p–4K), target FPS (`60`/`120`/`Unlimited`), upscaler (`FSR 1`, `FSR 3.1`, `DLSS`), sharpening, async shader compilation, MSAA, frame generation, aspect ratio, and one-click GPU auto-optimize.
  - **Built-in Live Log & Controller Info:** Real-time engine output viewer, Vulkan GPU detection, and save/dump status indicator.

---

## End-User Installation (Portable Release)

If you downloaded a packaged release build, no compiler or Python installation is required. See the full step-by-step guide in **[INSTALL.md](INSTALL.md)**:

```text
Persona4_Dancing_PC/                 <- Portable folder (place on any drive, e.g. J:\Games\)
├── Persona 4 Dancing All Night.exe  <- Run this launcher
├── p4dan_pc.exe                     <- Native runtime & Vulkan engine
├── *.dll                            <- MSYS2 CLANG64 runtime DLLs
├── game_data/                       <- (Optional) Put your CUSA12112 uroot/app0 dump here
├── out/                             <- Auto-generated on first launch
├── user/                            <- Save data (/savedata0) & shader caches
└── bbport.ini                       <- Graphics & input configuration
```

1. Double-click **`Persona 4 Dancing All Night.exe`**.
2. Click **`Folder Game`** (unless placed in `./game_data`) and select your `CUSA12112`, `app0`, or `uroot` dump folder.
3. Click **`MAINKAN GAME`** — first-run boot files are prepared automatically.

---

## Building from Source (Windows MSYS2 CLANG64)

### 1. Install Toolchain & Dependencies

Install [MSYS2](https://www.msys2.org), open the **MSYS2 CLANG64** shell, and install packages (see [packaging/windows/README.md](packaging/windows/README.md) for details):

```bash
pacman -S --needed git patch \
  mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python} \
  mingw-w64-clang-x86_64-{vulkan-headers,vulkan-loader,vulkan-memory-allocator,glslang} \
  mingw-w64-clang-x86_64-{sdl3,fmt,boost,robin-map,xxhash,ffmpeg,zydis} \
  mingw-w64-clang-x86_64-{spirv-tools,spirv-headers,spirv-cross}
```

### 2. Clone & Build the Engine

```bash
git clone --recursive https://github.com/krixsan/Persona-4-Dance-All-Night.git
cd Persona-4-Dance-All-Night
./build.sh
```

This compiles **`out/sacredfire.exe`** and **`out/bb-gpu-capabilities.exe`**.
- Note: Icon embedding (`packaging/windows/icons/p4dan.ico`) is optional and automatically enabled if `p4dan.ico` is present locally.

### 3. Build the Standalone Launcher & Portable Release (Optional)

With Python (`pillow` and `pyinstaller` installed):

```powershell
# Extract local icon/art from your dump (optional) and compile the standalone launcher EXE:
python launcher/build_launcher.py --game-dir "D:\PS4_Dumps\CUSA12112"

# Or assemble a complete self-contained portable release folder:
python launcher/build_launcher.py --game-dir "D:\PS4_Dumps\CUSA12112" --package "dist\Persona4_Dancing_PC"
```

To run the launcher directly from source without compiling an EXE:

```powershell
python launcher/P4DAN_Launcher.pyw
```

### Command-Line Run (Developers)

```bash
BB_GAME_DIR="/path/to/CUSA12112/app0/uroot" python run.py
```

---

## Controls

- **Gamepad:** XInput / DualShock controllers detected automatically via SDL3.
- **Keyboard:** `WASD` (Left Stick), Arrow keys (Right Stick), `I J K L` (D-Pad), `Space` (Cross), `LShift` (Circle), `E` (Square), `Q` (Triangle), `Enter` (Options).
- **In-Game Overlay Menu:** Press `Insert` or `L3 + R3` anytime to adjust resolution, FPS cap, and upscaling live.

---

## Documentation & License

- [INSTALL.md](INSTALL.md) — End-user setup guide
- [docs/persona4/BUILD_NOTES.md](docs/persona4/BUILD_NOTES.md) — Engine build & runtime notes
- [docs/persona4/WORK_REPORT_VIDEODEC.md](docs/persona4/WORK_REPORT_VIDEODEC.md) — Video decoding investigation & fixes
- [docs/persona4/PATCH_MAP.md](docs/persona4/PATCH_MAP.md) — `CUSA12112` patch & `/app0` mount map

This project is licensed under **GPL-2.0**. Built upon the SacredFire / `bbport` compatibility layer and `shadPS4` video core components.
