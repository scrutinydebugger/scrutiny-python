cmake_minimum_required(VERSION 3.14)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/609281088cfefc76f9d0ce82e1ff6c30cc3591e5.zip
)

# For Windows: Prevent overriding the parent project's compiler/linker settings
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

enable_testing()

project(scrutiny_unittest)
add_executable(${PROJECT_NAME}
    ${CMAKE_CURRENT_SOURCE_DIR}/scrutiny_test.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/test_timebase.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/test_crc.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/protocol/test_protocol_rx_parsing.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/protocol/test_protocol_tx_parsing.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/protocol/test_comm_handler.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/commands/test_get_info.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/commands/test_comm_control.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/commands/test_memory_control.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/commands/test_user_command.cpp
    )
target_include_directories(${PROJECT_NAME}
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}
    )
target_link_libraries(${PROJECT_NAME}
    scrutiny-lib
    gtest_main
    )

if(MSVC)
    target_compile_options(scrutiny-lib PRIVATE /W4 /Od)
    target_compile_options(${PROJECT_NAME} PRIVATE /W4 /Od)
else()
    target_compile_options(scrutiny-lib PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(${PROJECT_NAME} PRIVATE -Wall -Wextra -Wpedantic)
endif()

include(GoogleTest)
gtest_discover_tests(${PROJECT_NAME})
