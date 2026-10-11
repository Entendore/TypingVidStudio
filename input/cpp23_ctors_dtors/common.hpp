#pragma once

#include <expected>
#include <string>
#include <utility>
#include <algorithm>
#include <cstddef>
#include <stdexcept>
#include <vector>
#include <memory>

// Helper macro to suppress unused warnings for our didactic run() functions
#define USE_SECTION(X) namespace X { void run(); } struct AutoRun_##X { AutoRun_##X() { X::run(); } } auto_run_##X;
