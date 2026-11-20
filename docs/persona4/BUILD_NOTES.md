# Persona 4 Dancing All Night port notes

## Current status

- Target: CUSA12112, app version 01.00 (verified from the extracted `param.sfo`).
- Milestone: M0-C source-only sanitization, M0-D Windows build, M1 runtime bring-up, and M3
  videodec integration are complete. The game now boots to the title screen, Story Mode, the
  1920x1088 opening movie, and the rhythm tutorial stage. M3 evidence and limits are below.
- Runtime profile is named `generic`; it is experimental and does not imply game compatibility.
- No P4-specific HLE stubs or memory patches have been inferred from CTR offsets.

## Local input

- Extracted package root: `00_GAME_DUMP/CUSA12112/app0/uroot`.
- Original `eboot.bin` is a fake-signed SELF (`4F 15 3D 1D`) and has not been changed.
- `eboot.elf` is the locally generated ELF (`7F 45 4C 46`), ELF64 little-endian x86-64, with 11
  validated program headers. The runner and image-preparation scripts prefer this file when it is
  present.
- Package `sce_module` files are retained in the dump. `libc.prx` and `libSceFios2.prx` were parsed
  and linked successfully into the probe image.

## Sanitization and initial checks

- Default host game path points at the extracted P4 package; guest `/app0` remains the runtime
  mount contract.
- CTR XML patches, trophy metadata, and ultrawide scripts were moved under `legacy/` locations.
  Default patch scanning does not recurse into those folders.
- CTR launcher/package artifacts were moved under `legacy/`; game-specific patch and render-scale
  controls are disabled by default.
- The generic patch compiler and patch blob reader remain available; no game-specific patches are
  enabled.
- The launcher is excluded from the default Windows build.
- Targeted Python tests passed: game checker, generic patch compiler, DLC content profile, ELF
  preparation, and libc linking.
- The full Python discovery run had pre-existing Windows/environment limitations: symlink tests
  require Developer Mode/privilege; a test invoking `bash` cannot find it on Windows; one packaged
  Vulkan test assumes Linux path semantics. These were not failures in the changed logic.

## Build and runtime outcome

- Windows build completed with `./build.sh` in MSYS2 CLANG64 and produced
  `03_PERSONA4_PORT/out/sacredfire.exe` (`v0.4-windows`). CMake emitted policy/deprecation
  warnings; the build exited successfully.
- `ui-composition-test.exe` passed.
- In the initial M0 validation, `settings-test` and `upscaler-support-test` did not build on Windows
  because they used POSIX APIs; M1 replaced those calls with portable helpers and both now pass.
- A 60-second `run.py` smoke launch prepared the image and reached a ready Vulkan window. The
  runtime mapped 9 segments and applied 14,278 relocations, then crashed on the guest main thread:
  read access to `0xffffffffffffffff` at `sacredfire.exe+0x56ec`; process exit code 3. No gameplay
  boot was observed. The complete launch log is `03_PERSONA4_PORT/last_run.log`.
- The generated image linked `libc.prx` and `libSceFios2.prx`; 459 imports remained for the host
  runtime at module-link time. This does not establish that those imports are correctly implemented
  or that the crash is caused by any particular import.

The successful native build and Vulkan initialization do not establish that Persona 4 is playable.
The later startup diagnosis and current host-memory blocker are recorded below.

## M1 follow-up

- The Windows settings and upscaler tests now use portable environment/temp-file helpers and both
  build and pass. The upscaler tests explicitly enable the feature through `BB_UPSCALER`, matching
  the runtime's default-off policy for unverified game-specific rendering.
- Crash `sacredfire.exe+0x56ec` resolved to `runtime_set_procparam` in `src/runtime.c`. That
  diagnostic treated an unverified guest `SceLibcParam` extension as host pointers; the executable
  contains sentinel/non-pointer values there. The runtime now preserves and returns the original
  procparam block without decoding that extension. The initial fault was passed in a subsequent
  run.
- A boot iteration then reached the guest entry, initialized libc and FIOS worker threads, and
  stopped at the first called unsupported import, `sem_init` (`pDuPEf3m4fI#libScePosix`).
  Implemented the five imported POSIX semaphore operations with process-local state:
  `sem_init`, `sem_destroy`, `sem_wait`, `sem_post`, and `sem_getvalue`.
- `--list-imports` confirms all five now resolve. Across the prepared image and linked modules it
  reports 251 runtime, 141 native, and 219 unresolved imports. No blanket success stubs were
  generated: an import list does not establish call signatures or safe return values, and stubbing
  all unresolved entries would turn required failures into misleading success.
- The post-change boot attempt could not get far enough to retest guest startup: Windows failed to
  commit a 6,080 MiB page-backed section (`CreateFileMapping2`, error 1450), raised debug exception
  `0xa0020013`, and exited with code 3. Available virtual commit was below the requested section
  size. No title screen or gameplay has been verified; rerun after increasing available pagefile
  capacity or freeing system commit.

## M1-3 follow-up

- The subsequent run successfully mapped 3,153,068,032 bytes of guest direct memory, initialized
  eight guest threads, and reached `_sceFiberInitializeImpl` at guest return offset `0x24ec11`.
- Implemented the six imported `libSceFiber` entry points with cooperative context switching.
  Windows uses native fibers with host-owned stacks; POSIX uses `ucontext` on the supplied context
  region. Unknown Fiber NIDs remain unsupported.
- The focused `fiber-test` passes fiber-to-fiber switching, return-to-thread, resume arguments,
  and self lookup on Windows. The full runtime build also succeeds.
- At that point, the latest 60-second game smoke run stopped before guest entry with
  `CreateFileMapping2` error
  1455 while creating 6,080 MiB of guest memory. Therefore the Fiber HLE is unit-tested but not
  yet boot-tested; no menu or rendered frame is verified.

## M1-4B follow-up

- Changed the Windows guest-memory section to `SEC_RESERVE` and commit pages in the access-violation
  handler. The mapped guest permissions are obtained from the runtime VMA table because
  `VirtualQuery` reports `Protect=0` for uncommitted `MEM_RESERVE` section pages.
- The runtime test now installs a minimal VEH dispatcher for the test process and the test image
  disables high-entropy ASLR so the PS4 guest address range can be reserved. Shared direct-memory
  aliases and zero-on-reuse pass; the lazy-commit diagnostic confirms page commitment on access.
- `./build.sh` succeeds. A bounded `run.py` smoke launch reserved 6,080 MiB, mapped 3,153,068,032
  bytes of direct memory, committed pages on first access, created 18 guest threads, and initialized
  audio. It then stopped with exit code 20 at the targeted unsupported import
  `qQJfO8HAiaY#libSceNpManager` (index 58). This is progress past the memory blocker, not a boot to
  title screen.

## M1-5 follow-up

- Mapped the observed NID `qQJfO8HAiaY` to `sceNpRegisterStateCallbackA` using the generated import
  names and added it to the existing signed-out/offline NpManager exports. It reuses the established
  offline callback-registration behavior; no unobserved NpManager imports were added.
- The runtime test resolves this exact NID, passes, and the Windows game build succeeds.
- The bounded boot run passes the NpManager import and stops at the next unsupported import:
  `1n37q1Bvc5Y#libSceSystemService` (index 268). It still does not reach title/menu or render a
  frame.

## M1-6 follow-up

- The import at index 268 is `sceSystemServiceGetDisplaySafeAreaInfo`, not event reception. Added
  only that observed NID to the existing SystemService implementation: it returns a 1.0 safe-area
  ratio with reserved bytes cleared, and reports the existing invalid-parameter error for a null
  output pointer. Existing `ReceiveEvent` behavior remains `SYSTEM_NO_EVENT` when there is no event.
- Runtime tests verify NID resolution, output initialization, ratio, and null-pointer error; the
  Windows build succeeds.
- A bounded smoke run passed this import and created additional CRI video-decoder worker threads.
  It stopped at `BQ3tey0JmQM#libSceCommonDialog` (index 264), exit code 20. No frame or title/menu
  has been verified.

## M1-7 follow-up

- The blocked import `BQ3tey0JmQM#libSceCommonDialog` resolves to `sceCommonDialogIsUsed`. Added
  only this observed import, returning false while the runtime has no active CommonDialog UI.
  Existing `sceCommonDialogInitialize` and other dialog APIs were not changed.
- The runtime test verifies this NID resolves and returns false; the runtime test and Windows build
  pass.
- The bounded smoke run remained active until the external 90-second limit. It logged repeated GPU
  command-buffer submissions and made progress past the previous import stop, but logged no
  explicit flip/frame counter or new unsupported import before it was stopped. A visible first
  frame/title screen is therefore not confirmed.

## M1-8 follow-up

- Confirmed the existing presentation path: `sceGnmSubmitAndFlipCommandBuffers` patches the flip
  request and submits through GNM; VideoOut's `Flip` calls the Vulkan presenter, and its frame log
  writes one CSV row per flip.
- A bounded 20-second Windows smoke run with `BB_SAVE_LOG=1` created a responsive window titled
  "Persona 4: Dancing All Night". The per-flip CSV contained 881 rows over 14.8 seconds
  (approximately 59.5 flips/sec), 102,512 draws, and 1,761 submissions. Runtime reports showed
  about 102-124 draws/frame and `sceGnmSubmitDone` once per frame.
- No new unsupported-import stop or runtime fault was logged before the process was stopped.
  The window's existence and active presentation are verified, but no screenshot or human
  confirmation of visible game imagery was available during the run; the user later confirmed the
  window appeared black/blank. A rendered title screen is not yet confirmed.

## M3 videodec and story/gameplay smoke

- Added the six imported `libSceVideodec` entry points used by CUSA12112 (`qkgRiwHyheU`,
  `q0W5GJMovMs`, `U0kpGF1cl90`, `jeigLlKdp5I`, `leCAscipfFY`, `f8AgDv-1X8A`) from upstream
  shadPS4 at `b4e7ae776071ceb1dd35004577a8719481e1d258`. The decoder uses the FFmpeg H.264
  software decoder and converts decoded frames to NV12 for the guest frame buffer.
- `out/sacredfire.exe` now registers 334 HLE symbols. The previous
  `STOP: first unsupported PS4 import: leCAscipfFY#libSceVideodec` is gone.
- Verified at runtime: title screen, Story Mode prologue, the 1920x1088 opening movie (moving
  anime frames, not a still), the story cutscene path, and the rhythm tutorial stage
  "MIDNIGHT STAGE" with a live score/progress bar and 60 FPS presentation. Audio ports and the
  ADX2 guest threads initialize through WASAPI.
- Hardened the HLE surface: null argument checks for decode/delete/flush/reset, checked
  `av_frame_alloc` / `av_frame_get_buffer` / `sws_getCachedContext`, cached swscale context
  recreation, and `ORBIS_VIDEODEC_ERROR_API_FAIL` instead of an assertion when NV12 conversion
  fails.
- Evidence: `05_LOGS/watch_00_title.png`, `watch_20s.png`, `watch_30s.png`, `watch_40s.png`
  (opening movie), `mash_300.png` / `mash_end.png` (prologue), `gameplay_01.png` through
  `gameplay_03.png` (tutorial stage and return to story).
- Laporan kerja lengkap: `07_DOCS/WORK_REPORT_VIDEODEC.md`.

