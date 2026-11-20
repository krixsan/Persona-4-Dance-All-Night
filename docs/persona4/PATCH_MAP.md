# Persona 4 Dancing All Night source-only map

**Target:** CUSA12112, version 01.00 (verified from the extracted `param.sfo`)  
**Executable:** `00_GAME_DUMP/CUSA12112/app0/uroot/eboot.elf`  
**Port worktree:** `03_PERSONA4_PORT`, branch `persona4-cusa12112`

## M0-C sanitization

- The generic checker validates the executable format and reports a `generic` profile. It does
  not claim Persona 4 compatibility or playability.
- `run.py` and `run.sh` default to the extracted host folder
  `00_GAME_DUMP/CUSA12112/app0/uroot`; the guest-visible `/app0` mount is unchanged.
- The runtime uses the decrypted `eboot.elf` when present, leaving the original SELF `eboot.bin`
  untouched.
- CTR XML patches are retained under `03_PERSONA4_PORT/patches/legacy/` and are excluded from
  the default patch scan. The generic XML patch compiler remains available for explicitly supplied
  patches.
- CTR trophy fallback data, launcher/package artifacts, and ultrawide tooling are retained under
  `03_PERSONA4_PORT/legacy/`.
- Game-patch controls and CTR render-scale controls are hidden unless
  `LEGACY_GAME_HOOKS=ON`; the default menu title is experimental and generic.
- The CTR launcher is excluded from the default Windows build; its CMake target requires
  `LEGACY_GAME_HOOKS=ON`.
- The source's generic `/app0` guest mount and patch-blob reader are preserved.

## Patch evidence and limits

The original patch addresses and XML bytes are preserved as legacy evidence. They are not applied
to Persona 4. No address has been declared generic based on the Persona 4 executable, and no
CTR address has been reinterpreted as a P4 address. A matching CTR executable and REA are still
required to analyze those legacy offsets.

## Verification

- `CUSA13795`, `CUSA03173`, and `install_game_hooks` are absent from active `src/`.
- P4's executable was parsed and prepared using `eboot.elf`; `eboot.bin` remains unchanged.
- The runtime module linker accepted `libc.prx` and `libSceFios2.prx`; 459 imports remain for the
  HLE runtime to resolve.
- Build and runtime launch results are recorded in `BUILD_NOTES.md`. A successful build or process
  start is not evidence that the game is playable.

## Preserved `/app0` contract

`src/runtime_file.c` maps the guest path `/app0` to the host folder supplied by the runner. Do not
replace guest paths in the game with host-relative paths. Only the runner's default host folder
changes for this dump.
