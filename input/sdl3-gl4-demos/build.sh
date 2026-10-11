#!/usr/bin/env bash
# =============================================================================
#  build.sh - tiny convenience wrapper around CMake for this demo suite
# =============================================================================
#  ./build.sh                    configure + build all demos (Release)
#  ./build.sh run demo_shadows   build, then run one demo (see ./build.sh list)
#  ./build.sh list               list available demo targets
#  ./build.sh debug              configure/build a Debug build (GL_CHECK active)
#  ./build.sh clean              delete the build directory
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

build_type=Release
cmd="${1:-build}"
[ $# -gt 0 ] && shift
[ "$cmd" = debug ] && { build_type=Debug; }

case "$cmd" in
    build|configure|debug)
        cmake -B build -DCMAKE_BUILD_TYPE="$build_type"
        jobs=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
        cmake --build build -j "$jobs"
        echo
        echo "Binaries are in ./build - try: ./build.sh run demo_triangle"
        ;;
    run)
        demo="${1:?usage: ./build.sh run <demo>  (see ./build.sh list)}"
        cmake -B build -DCMAKE_BUILD_TYPE="$build_type" >/dev/null
        cmake --build build -j >/dev/null 2>&1
        exec "./build/$demo" "${@:2}"
        ;;
    list)
        echo "Available demos:"
        for f in [0-9][0-9]_*.cpp; do
            name="${f%.*}"                        # e.g. 09_shadows
            printf '  demo_%s\n' "${name#*_}"     #    demo_shadows
        done
        ;;
    clean)
        rm -rf build
        echo "removed ./build"
        ;;
    *)
        echo "unknown command: $cmd (see the header of build.sh)"
        exit 1
        ;;
esac
