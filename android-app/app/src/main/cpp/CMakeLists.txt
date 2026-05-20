cmake_minimum_required(VERSION 3.22.1)

project(naturavision_llama LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(LLAMA_CPP_DIR "C:/tmp/llama.cpp" CACHE PATH "Path to a local llama.cpp checkout")
if(NOT EXISTS "${LLAMA_CPP_DIR}/CMakeLists.txt")
    message(FATAL_ERROR "LLAMA_CPP_DIR must point to a llama.cpp checkout. Current value: ${LLAMA_CPP_DIR}")
endif()

set(LLAMA_BUILD_COMMON ON CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_UI OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS ON CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)
set(LLAMA_OPENSSL OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_LLAMAFILE OFF CACHE BOOL "" FORCE)
set(Vulkan_INCLUDE_DIR "C:/tmp/Vulkan-Headers/include" CACHE PATH "" FORCE)
set(Vulkan_INCLUDE_DIRS "C:/tmp/Vulkan-Headers/include" CACHE PATH "" FORCE)
set(SPIRV-Headers_INCLUDE_DIR "C:/tmp/SPIRV-Headers/include" CACHE PATH "" FORCE)
set(SPIRV-Headers_DIR "${CMAKE_CURRENT_LIST_DIR}/cmake" CACHE PATH "" FORCE)
set(GGML_VULKAN_SHADERS_GEN_TOOLCHAIN "${CMAKE_CURRENT_LIST_DIR}/cmake/windows-host-msvc-toolchain.cmake" CACHE FILEPATH "" FORCE)
set(Vulkan_GLSLC_EXECUTABLE "C:/tmp/naturavision-android-sdk/ndk/27.0.12077973/shader-tools/windows-x86_64/glslc.exe" CACHE FILEPATH "" FORCE)
set(GGML_VULKAN ON CACHE BOOL "" FORCE)

include_directories("C:/tmp/SPIRV-Headers/include")

add_subdirectory("${LLAMA_CPP_DIR}" llama-build)

add_library(naturavision-llama SHARED
    naturavision_llama.cpp
)

target_include_directories(naturavision-llama PRIVATE
    "${LLAMA_CPP_DIR}"
    "${LLAMA_CPP_DIR}/include"
    "${LLAMA_CPP_DIR}/ggml/include"
    "${LLAMA_CPP_DIR}/ggml/src"
    "${LLAMA_CPP_DIR}/tools/mtmd"
)

target_link_libraries(naturavision-llama
    llama
    mtmd
    android
    log
)
