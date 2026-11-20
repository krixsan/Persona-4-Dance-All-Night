# Panduan Instalasi — Persona 4: Dancing All Night PC Port

Cukup **3 langkah mudah** (tidak perlu Python, compiler, atau command line):

## 1. Siapkan Folder Game & Dump PS4
Ekstrak rilis PC Port ke folder biasa (contoh: `D:\Games\Persona4_Dancing_PC\`), lalu siapkan dump game PS4 *Persona 4: Dancing All Night* (`CUSA12112`) milikmu yang **lengkap**:

```text
Persona4_Dancing_PC/                 <- Folder aplikasi PC
├── Persona 4 Dancing All Night.exe  <- KLIK INI untuk buka Launcher & main
├── p4dan_pc.exe                     <- Engine runtime utama + Vulkan
├── *.dll                            <- DLL runtime (SDL3, FFmpeg, dll.)
├── assets/                          <- Artwork & ikon game
├── scripts/                         <- Auto-setup modul PS4
├── out/                             <- Otomatis dibuat Launcher saat pertama jalan
├── user/                            <- Save data (/savedata0) & shader cache
└── bbport.ini                       <- Konfigurasi grafis & kontrol

Folder_Dump_PS4/CUSA12112/app0/uroot/ <- Dump PS4 lengkap (boleh ditaruh di mana saja,
├── eboot.bin                           atau taruh di ./game_data di dalam folder game)
├── data/
│   ├── data.cpk
│   └── ps4.cpk
├── sce_module/                      <- libc.prx, libSceFios2.prx, dll.
└── sce_sys/                         <- param.sfo, icon0.png, dll.
```

> **Catatan:** Jangan hanya mengambil file `eboot.bin` saja. Pastikan `data/ps4.cpk`, `data/data.cpk`, `sce_module/`, dan `sce_sys/` ada.

## 2. Jalankan Launcher
1. Klik dua kali **`Persona 4 Dancing All Night.exe`**.
2. Klik **`📂 Folder Game`** lalu pilih folder dump PS4 kamu (boleh langsung pilih folder `CUSA12112`, `app0`, atau `uroot` — launcher otomatis mendeteksi isinya).
3. Saat pertama kali dijalankan, launcher otomatis menyiapkan file boot (`out/boot-linked.bin`, `content.bin`, `import_names.txt`, `patches.bin`) secara otomatis.

## 3. Atur Grafis & Mainkan
- Pilih **Resolusi** (`1920×1080`), **Target FPS** (`60 FPS` disarankan untuk timing ritme), **Mode Upscaler** (`FSR 1` / `FSR 3.1` / `DLSS`), atau klik **`✨ Auto-Optimize`**.
- Tekan **`MAINKAN GAME`**.

### Kontrol Singkat
- **Gamepad:** XInput / DualShock terdeteksi otomatis.
- **Keyboard:** `WASD` (L-Stick), `Panah` (R-Stick), `I J K L` (D-Pad), `Space` (Cross), `LShift` (Circle), `E` (Square), `Q` (Triangle), `Enter` (Options).
- **Menu In-Game:** Tekan `Insert` atau `L3 + R3` kapan saja untuk atur grafis/FPS live.
