# Building the project's own CMakeLists.txt with warnings as errors, sanitizers and coverage (added by /quality-init),
# so the project's build stays untouched and the gate flags live only here
cmake_minimum_required(VERSION 3.20)
project(quality_gate LANGUAGES C CXX)

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
add_compile_options(-Wall -Wextra -Wpedantic -Werror -fsanitize=address,undefined -fno-omit-frame-pointer --coverage)
add_link_options(-fsanitize=address,undefined --coverage)

enable_testing()
add_subdirectory(.. project)
