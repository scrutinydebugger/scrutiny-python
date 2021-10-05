cmake_minimum_required(VERSION 3.14)
project(scrutiny_unittest)

# GoogleTest requires at least C++11
set(CMAKE_CXX_STANDARD 11)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/609281088cfefc76f9d0ce82e1ff6c30cc3591e5.zip
)

# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

enable_testing()

include("../sources.cmake")
list(TRANSFORM SCRUTINY_SOURCES PREPEND  "../")
list(TRANSFORM SCRUTINY_INCLUDE_DIR PREPEND  "../")

include_directories(${SCRUTINY_INCLUDE_DIR})
include_directories(".")

add_library(scrutiny ${SCRUTINY_SOURCES})

set(TARGET_NAME scrutiny_test)
add_executable(${TARGET_NAME} 
  scrutiny_test.cpp
  test_timebase.cpp
  test_crc.cpp
  protocol/test_protocol_rx_parsing.cpp
  protocol/test_protocol_tx_parsing.cpp
  protocol/test_comm_handler.cpp
  commands/test_command_get_info.cpp
  commands/test_comm_control.cpp
  )

target_link_libraries(
  ${TARGET_NAME}
  scrutiny
  gtest_main
)

if(MSVC)
  target_compile_options(scrutiny PRIVATE /W4 /Od)
  target_compile_options(${TARGET_NAME} PRIVATE /W4 /Od)
else()
  target_compile_options(scrutiny PRIVATE -Wall -Wextra -Wpedantic)
  target_compile_options(${TARGET_NAME} PRIVATE -Wall -Wextra -Wpedantic)
endif()


include(GoogleTest)
gtest_discover_tests(${TARGET_NAME})
