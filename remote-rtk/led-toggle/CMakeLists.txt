cmake_minimum_required(VERSION 3.10)
project(led-toggle)

set (CMAKE_C_STANDARD 11)

# Find threads
find_package(Threads REQUIRED)

# Find libgpiod
find_library(GPIOD_LIB gpiod REQUIRED)

# Executable implementation
add_executable(led-toggle led-toggle.c)
target_link_libraries(led-toggle ${CMAKE_THREAD_LIBS_INIT} ${GPIOD_LIB})
