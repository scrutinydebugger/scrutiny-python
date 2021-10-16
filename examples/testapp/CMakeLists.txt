project(testapp)

add_executable(${PROJECT_NAME})

target_sources(${PROJECT_NAME}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/src/file1.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/file2.cpp
        ${CMAKE_CURRENT_SOURCE_DIR}/src/main.cpp
    )

target_link_libraries(${PROJECT_NAME}

    )

if(MSVC)    # MSVC doesn't support dwarf output. We still allows build of testapp.
    target_compile_options(scrutiny-lib PRIVATE /W4 /Od)
    target_compile_options(${PROJECT_NAME} PRIVATE /W4 /Od)
else()
target_compile_options(${PROJECT_NAME}
    PRIVATE
        -no-pie  
        -gdwarf
        -O0
    )

target_link_options(${PROJECT_NAME}
    PUBLIC
        -no-pie
        -gdwarf
    )
endif()



