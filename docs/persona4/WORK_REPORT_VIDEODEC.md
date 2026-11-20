# Laporan Pekerjaan: Port libSceVideodec

**Proyek:** Persona 4 Dancing All Night, CUSA12112 versi 01.00  
**Tanggal:** 10 November 2026  
**Build:** `03_PERSONA4_PORT/out/sacredfire.exe` (`v0.4-windows`)  
**Status:** Selesai untuk acceptance praktis. File PRD tidak ditemukan di workspace.

## Hasil

Game berhasil melewati import `leCAscipfFY#libSceVideodec`, masuk title screen, membuka Story Mode, memutar opening movie 1920x1088, melewati alur story yang pada run sebelumnya berhenti karena assertion, dan masuk stage ritme **MIDNIGHT STAGE**. Run terakhir tidak mencatat `STOP`, assertion, atau error videodec. Build mendaftarkan **334 HLE symbol**.

Game juga sudah mencapai auto-save. Proses terakhir masih hidup dan merespons saat laporan ini dibuat.

## Masalah awal

Sebelum perubahan, boot berhenti di import pertama yang belum ditangani:

```text
STOP: first unsupported PS4 import: leCAscipfFY#libSceVideodec
```

Game memakai `libSceVideodec` untuk decode video. Tanpa HLE, alur story tidak bisa membuka movie. Frame hasil decode FFmpeg berformat `yuv420p`, sedangkan frame buffer guest memakai NV12, jadi ada tahap konversi dan penyalinan memori yang harus benar.

## Ruang lingkup

- Hanya enam NID `libSceVideodec` yang diimpor game.
- Sumber diambil dari upstream shadPS4 commit `b4e7ae776071ceb1dd35004577a8719481e1d258`, bukan `main`.
- FFmpeg sudah terhubung di `gpu/CMakeLists.txt`.
- Tidak ada perubahan pada memory, Fiber, atau SystemService.
- Decoder `vdecsw` dan `videodec2` tidak diaktifkan.
- `sceVideodecMapMemory` tetap stub; game tidak memanggilnya.

## Perubahan teknis

| Area | File | Isi |
| --- | --- | --- |
| HLE entry point | `gpu/shadps4/core/libraries/videodec/videodec.cpp` | Enam fungsi yang dipakai game plus stub `MapMemory`, validasi argumen, query resource, registrasi NID |
| Decoder | `.../videodec_impl.cpp`, `.../videodec_impl.h` | Kelas `VdecDecoder`, FFmpeg H.264, konversi NV12, flush, reset |
| ABI | `.../videodec.h`, `.../videodec_error.h` | Struct dan kode error PS4 |
| Copy frame | `.../video_utils.cpp` | `CopyNV12Data` yang sudah ada di port, dipakai untuk menyalin hasil konversi ke frame buffer guest |
| Registrasi | `gpu/shim/bbgpu.cpp` | Panggilan `Libraries::Videodec::RegisterLib` |
| Build | `gpu/CMakeLists.txt` | Source videodec dan linkage FFmpeg |
| Dokumentasi | `07_DOCS/BUILD_NOTES.md` | Catatan milestone M3 dan bukti runtime |

### Alur decode

1. Game memanggil `sceVideodecQueryResourceInfo` untuk menghitung kebutuhan memori dan ukuran frame buffer.
2. `sceVideodecCreateDecoder` membuat `VdecDecoder` dan membuka decoder H.264 FFmpeg.
3. `sceVideodecDecode` membungkus AU guest menjadi `AVPacket`, mengirim ke FFmpeg, lalu mengambil `AVFrame`.
4. Frame `yuv420p` dikonversi ke NV12 lewat `sws_getCachedContext` dan `sws_scale`.
5. `CopyNV12Data` menyalin frame ke buffer guest dengan pitch align 64 dan tinggi align 16.
6. `OrbisVideodecPictureInfo` diisi dengan lebar, pitch, tinggi, crop, PTS, dan `attachedData`.
7. `sceVideodecFlush` mengirim packet null untuk mengeluarkan frame yang tertahan.
8. `sceVideodecDeleteDecoder` membebaskan konteks dan mengosongkan handle.

Resource info memakai rumus:

- frame size = align(width, 256) × align(height, 16) × 1.5
- `maxFrameBufferSize` = frame size + `0x4000`
- CPU-GPU memory = (frame size + `0x4000`) × (DPB + 2) + 8 MiB
- CPU memory = 16 MiB

Contoh dari log: decoder opening movie `1920x1088` mendapat `maxFrameBufferSize` 3.358.720 byte; probe `960x544` mendapat 851.968 byte.

## Penanganan error

Semua entry point sekarang memeriksa pointer null dan ukuran struct. `Decode`, `Flush`, `DeleteDecoder`, dan `Reset` menolak handle yang tidak valid. Alokasi `AVPacket`, `AVFrame`, `av_frame_get_buffer`, dan `sws_getCachedContext` diperiksa; kalau gagal, fungsi mengembalikan `ORBIS_VIDEODEC_ERROR_API_FAIL` dan menulis log, bukan memicu assertion.

Konteks swscale disimpan per decoder dan dibuat ulang lewat `sws_getCachedContext` saat ukuran atau format source berubah. Ini penting karena decoder yang sama bisa menerima frame dengan parameter berbeda selama probing.

## Bukti pengujian

Build berhasil lewat `06_TOOLS/bb_build.sh`. Build dan runtime report menunjukkan 334 HLE symbol, naik dari 327.

Pengujian runtime:

- Title screen tampil.
- Story Mode dan prologue berjalan.
- Opening movie 1920x1088 memutar frame anime bergerak. Screenshot: `05_LOGS/watch_20s.png`, `watch_30s.png`, `watch_40s.png`.
- AU yang ditangkap dari game valid: H.264 High, 1920x1088, `yuv420p`. File: `05_LOGS/videodec_au/all_au.h264`; frame hasil decode offline: `05_LOGS/videodec_au/frame_04.png`.
- Alur story yang pada run sebelumnya berhenti karena assertion selesai tanpa crash. Screenshot: `05_LOGS/mash_300.png`, `mash_end.png`.
- Stage ritme **MIDNIGHT STAGE** masuk dan berjalan dengan score/progress. Screenshot: `05_LOGS/gameplay_01.png` sampai `gameplay_03.png`.
- Setelah stage, game kembali ke story dan melakukan auto-save. Screenshot: `05_LOGS/final_state.png`.
- Log run terakhir: `05_LOGS/watch_stdout.txt`; tidak ada `STOP`, assertion, atau `<Error>`.
- Audio: WASAPI membuka port 0, 1, 8, 9, 13, 17; thread `threadSeqSndAdx2` dan `threadExecuteSndAdx2` dibuat.

## Acceptance

| Kriteria | Hasil |
| --- | --- |
| Boot melewati import `libSceVideodec` | Lulus |
| Title screen | Lulus |
| Story Mode dan prologue | Lulus |
| Decode movie 1920x1088 | Lulus |
| Alur story yang pada run sebelumnya berhenti karena assert | Lulus, tanpa crash |
| Gameplay stage ritme | Lulus |
| Auto-save | Lulus |
| Tidak ada STOP/assertion | Lulus |

## Batasan

- Tidak ada file PRD di workspace. Acceptance di atas disusun dari tujuan praktis: game bisa boot, cerita, memutar video, dan masuk gameplay.
- Stage tutorial berjalan dengan auto-play. Input manual untuk note belum diuji di stage non-tutorial.
- `CopyNV12Data` masih memakai `ASSERT` kalau frame buffer guest lebih kecil dari kebutuhan. Guard ukuran frame buffer belum ditambahkan; ini kandidat hardening berikutnya.
- Hanya H.264 yang ditangani. Game saat ini memakai `codecType=0`; jalur HEVC belum diaktifkan.
- Perubahan belum di-commit. Di worktree ada perubahan lain yang tidak terkait dan tidak boleh ikut masuk commit.

## Cara build dan run

```powershell
C:\msys64\usr\bin\bash.exe "F:\Project Porting Game PS4\Persona 4\06_TOOLS\bb_build.sh"
cd "F:\Project Porting Game PS4\Persona 4\03_PERSONA4_PORT"
python run.py
```

Environment variable yang berguna:

- `BB_GPU_LOG=info` untuk log HLE.
- `BB_SAVE_LOG=1` untuk menyimpan log ke folder `logs/`.
- `BB_TIMEOUT=0` untuk menonaktifkan batas waktu runner.
- `BB_VIDEODEC_DUMP=<folder>` untuk menangkap 64 AU pertama.

## Lampiran: NID

| NID | Fungsi |
| --- | --- |
| `qkgRiwHyheU` | `sceVideodecCreateDecoder` |
| `q0W5GJMovMs` | `sceVideodecDecode` |
| `U0kpGF1cl90` | `sceVideodecDeleteDecoder` |
| `jeigLlKdp5I` | `sceVideodecFlush` |
| `leCAscipfFY` | `sceVideodecQueryResourceInfo` |
| `f8AgDv-1X8A` | `sceVideodecReset` |
| `kg+lH0V61hM` | `sceVideodecMapMemory` (stub) |
