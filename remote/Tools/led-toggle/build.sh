#!/bin/bash

# Configuration
PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null & pwd)
BUILD_DIR="$PROJECT_DIR/build"

# Build project
do_build() {
    echo "--- Starting Build ---"
    # Create build directory if it doesn't exist
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR" || exit

    # Run CMake and Compile
    echo "Configuring and building..."
    cmake ..
    make
    echo "Build complete."
}

# Function to clean the project
do_clean() {
    echo "--- Cleaning Project ---"
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        echo "Build directory removed."
    else
        echo "Nothing to clean."
    fi
}

# main logic
case "$1" in
    make)
        do_build
        ;;
    clean)
        do_clean
        ;;
    *)
        echo "Usage: $0 {make|clean}"
        exit 1
        ;;
esac

