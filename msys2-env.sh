# Sourced by the Windows build/run scripts: puts the MSYS2 CLANG64 toolchain first on PATH.
# MSYS2_ROOT overrides the default F:/msys64 or C:/msys64.
for candidate in "${MSYS2_ROOT:-}" "/f/msys64" "/c/msys64"; do
    if [[ -n "$candidate" && -d "$candidate/clang64/bin" ]]; then
        export MSYS2_ROOT="$candidate"
        export PATH="$candidate/clang64/bin:$candidate/usr/bin:$PATH"
        export MSYSTEM=CLANG64
        break
    fi
done
