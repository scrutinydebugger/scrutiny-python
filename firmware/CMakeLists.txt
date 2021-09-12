project(libscrutinycpp)

add_library(${PROJECT_NAME} SHARED)
add_library(scrutiny::${PROJECT_NAME} ALIAS ${PROJECT_NAME})

target_include_directories(${PROJECT_NAME}
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/src
    )

target_sources(${PROJECT_NAME}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src/scrutiny/scrutiny.cpp
    )

target_compile_options(${PROJECT_NAME}
    PRIVATE
        -no-pie
        -Wall
        -Wextra
        -Wpedantic
        -Werror
    )
