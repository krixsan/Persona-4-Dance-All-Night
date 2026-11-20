// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cassert>
#include <cstdlib>
#include <fstream>
#include <string>

namespace TestPlatform {

inline std::string TempFile(const char* prefix) {
    const std::string path = std::string(prefix) + "-test.tmp";
    std::ofstream file(path);
    assert(file);
    return path;
}

inline void SetEnv(const char* name, const char* value) {
#ifdef _WIN32
    assert(_putenv_s(name, value) == 0);
#else
    assert(setenv(name, value, 1) == 0);
#endif
}

inline void UnsetEnv(const char* name) {
#ifdef _WIN32
    assert(_putenv_s(name, "") == 0);
#else
    assert(unsetenv(name) == 0);
#endif
}

} // namespace TestPlatform
