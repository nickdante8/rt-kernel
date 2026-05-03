cmake_minimum_required(VERSION 3.10)
project(led-toggle)

set (CMAKE_C_STANDARD 11)

# Find threads (required for pigpio)
find_package(Threads REQUIRED)

# Executable for pigpio implementation
add_executable(led-toggle led-toggle.c)
target_link_libraries(led-toggle pigpio ${CMAKE_THREAD_LIBS_INIT})
