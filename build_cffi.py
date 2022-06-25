#!/usr/bin/env python3
import glob
import os.path
import shutil
import struct
import subprocess
import platform
from distutils.command.build_ext import build_ext

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
NV2A_VSH_CPU_DIR = os.path.join(ROOT_DIR, "thirdparty", "nv2a_vsh_cpu")
BUILD_DIR = os.path.join(ROOT_DIR, "build")

if platform.system() == "Windows":
    LIBRARY_DIR = os.path.join(BUILD_DIR, "Release")
else:
    LIBRARY_DIR = BUILD_DIR


class FfiPreBuildExtension(build_ext):
    def pre_run(self, ext, ffi):
        try:
            out = subprocess.check_output(["cmake", "--version"])
        except OSError:
            raise RuntimeError("Please install CMake to build")

        cmake_config_args = [
            "-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON",
            "-Dnv2a_vsh_cpu_UNIT_TEST:BOOL=OFF",
            "-DCMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON",
        ]
        cmake_build_args = []
        if platform.system() == "Windows":
            is_64b = struct.calcsize("P") * 8 == 64
            cmake_config_args += ["-A", "x64" if is_64b else "Win32"]
            cmake_build_args += ["--config", "Release"]

        subprocess.check_call(
            [
                "cmake",
                "-B",
                "build",
                "-S",
                NV2A_VSH_CPU_DIR,
            ]
            + cmake_config_args,
            cwd=ROOT_DIR,
        )
        subprocess.check_call(
            [
                "cmake",
                "--build",
                "build",
                "--parallel",
                "--verbose",
                "--target",
                "nv2a_vsh_emulator",
            ]
            + cmake_build_args,
            cwd=ROOT_DIR,
        )


_SRC = """
#include "nv2a_vsh_emulator.h"
#include "nv2a_vsh_disassembler.h"
#include "nv2a_vsh_cpu.h"
"""

_CDEF = """
typedef struct {...;} Nv2aVshExecutionState;

typedef struct Nv2aVshCPUFullExecutionState_ {
  float input_regs[16 * 4];
  float output_regs[13 * 4];
  float temp_regs[12 * 4];
  float context_regs[192 * 4];
  float address_reg[4];
} Nv2aVshCPUFullExecutionState;

typedef enum Nv2aVshOpcode_ {
  NV2AOP_NOP = 0,
  NV2AOP_MOV,
  NV2AOP_MUL,
  NV2AOP_ADD,
  NV2AOP_MAD,
  NV2AOP_DP3,
  NV2AOP_DPH,
  NV2AOP_DP4,
  NV2AOP_DST,
  NV2AOP_MIN,
  NV2AOP_MAX,
  NV2AOP_SLT,
  NV2AOP_SGE,
  NV2AOP_ARL,
  NV2AOP_RCP,
  NV2AOP_RCC,
  NV2AOP_RSQ,
  NV2AOP_EXP,
  NV2AOP_LOG,
  NV2AOP_LIT
} Nv2aVshOpcode;

typedef enum Nv2aVshSwizzle_ {
  NV2ASW_X = 0,
  NV2ASW_Y,
  NV2ASW_Z,
  NV2ASW_W,
} Nv2aVshSwizzle;

typedef enum Nv2aVshWritemask_ {
  NV2AWM_W = 1,
  NV2AWM_Z,
  NV2AWM_ZW,
  NV2AWM_Y,
  NV2AWM_YW,
  NV2AWM_YZ,
  NV2AWM_YZW,
  NV2AWM_X,
  NV2AWM_XW,
  NV2AWM_XZ,
  NV2AWM_XZW,
  NV2AWM_XY,
  NV2AWM_XYW,
  NV2AWM_XYZ,
  NV2AWM_XYZW,
} Nv2aVshWritemask;

typedef enum Nv2aVshRegisterType_ {
  NV2ART_NONE = 0,  // This input/output slot is unused.
  NV2ART_TEMPORARY,
  NV2ART_INPUT,
  NV2ART_OUTPUT,
  NV2ART_CONTEXT,
  NV2ART_ADDRESS,  // A0
} Nv2aVshRegisterType;

typedef struct Nv2aVshOutput_ {
  Nv2aVshRegisterType type;
  uint32_t index;
  Nv2aVshWritemask writemask;
} Nv2aVshOutput;

typedef struct Nv2aVshInput_ {
  Nv2aVshRegisterType type;
  uint32_t index;
  uint8_t swizzle[4];
  uint8_t is_negated;
  uint8_t is_relative;
} Nv2aVshInput;

// Represents a single operation.
typedef struct Nv2aVshOperation_ {
  Nv2aVshOpcode opcode;
  Nv2aVshOutput outputs[2];
  Nv2aVshInput inputs[3];
} Nv2aVshOperation;

typedef struct Nv2aVshStep_ {
  Nv2aVshOperation mac;
  Nv2aVshOperation ilu;
  bool is_final;
} Nv2aVshStep;

typedef enum Nv2aVshParseResult_ {
  NV2AVPR_SUCCESS = 0,
  NV2AVPR_BAD_OUTPUT,
  NV2AVPR_BAD_PROGRAM,
  NV2AVPR_BAD_PROGRAM_SIZE,
  NV2AVPR_ARL_CONFLICT,
  NV2AVPR_BAD_MAC_OPCODE,
  NV2AVPR_BAD_ILU_OPCODE,
} Nv2aVshParseResult;

Nv2aVshExecutionState nv2a_vsh_emu_initialize_full_execution_state(
    Nv2aVshCPUFullExecutionState *state);
void nv2a_vsh_emu_apply(Nv2aVshExecutionState *state, const Nv2aVshStep *step);

Nv2aVshParseResult nv2a_vsh_parse_step(Nv2aVshStep *out, const uint32_t *token);
"""


def ffibuilder():
    from cffi import FFI

    ffi = FFI()
    ffi.set_source(
        "_nv2a_vsh_cpu",
        _SRC,
        libraries=["nv2a_vsh_emulator", "nv2a_vsh_disassembler", "nv2a_vsh_cpu"],
        include_dirs=[os.path.join(NV2A_VSH_CPU_DIR, "src")],
        library_dirs=[LIBRARY_DIR],
    )
    ffi.cdef(_CDEF)
    return ffi


if __name__ == "__main__":
    ffibuilder().compile(verbose=True)
