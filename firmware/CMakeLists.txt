cmake_minimum_required(VERSION 3.2)

project(scrutiny)
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_VERBOSE_MAKEFILE TRUE)

add_subdirectory(lib)
add_subdirectory(example/linux)
