project(linuxapp)

add_executable(${PROJECT_NAME})

target_sources(${PROJECT_NAME}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src/hello.cpp
    )

target_link_libraries(${PROJECT_NAME}
    scrutiny-lib
    )

target_compile_options(${PROJECT_NAME}
    PRIVATE
        -no-pie
        -Wall
        -Wextra
        -Wpedantic
        -Werror
    )

target_link_options(${PROJECT_NAME}
    PUBLIC
        -no-pie
        -Wl,-Map=output.map
    )
