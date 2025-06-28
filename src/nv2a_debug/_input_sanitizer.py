from __future__ import annotations

import re

import nv2a_vsh

_HEX_STRING = r"0x[0-9a-fA-F]+"
_CAP_HEX_VALUE = r"(" + _HEX_STRING + r")"

#  /* Slot 0: 0x00000000 0x0046AC00 0x69FEB800 0x28A00000 */
_XEMU_GLSL_SLOT_RE = re.compile(
    r"\s*/\*\s+Slot\s+(\d+):\s+("
    + _HEX_STRING
    + r")\s+("
    + _HEX_STRING
    + r")\s+("
    + _HEX_STRING
    + r")\s+("
    + _HEX_STRING
    + r")"
)


def sanitize_xemu_glsl(content: str) -> str | None:
    """Extracts original machine code from xemu vertex shader GLSL and returns decompiled vsh source."""
    shader = []

    last_slot = 0
    for match in re.finditer(_XEMU_GLSL_SLOT_RE, content):
        slot = int(match.group(1))
        ins_a = int(match.group(2), 16)
        ins_b = int(match.group(3), 16)
        ins_c = int(match.group(4), 16)
        ins_d = int(match.group(5), 16)

        if slot not in (0, last_slot + 1):
            msg = f"Missing instruction in xemu GLSL shader (expected slot {last_slot + 1} but found {slot}).\n\n{content}"
            raise ValueError(msg)

        shader.append((ins_a, ins_b, ins_c, ins_d))
        last_slot = slot

    if not shader:
        return None

    return "\n".join(nv2a_vsh.disassemble.disassemble(shader, explain=False))


_SUBCHANNEL = r"(\d+)"
_CLASS = _CAP_HEX_VALUE
_OP = _CAP_HEX_VALUE
_OPNAME = r"(?:\S+\s+)?"
_PARAM = _CAP_HEX_VALUE

# nv2a_pgraph_method 0: 0x97 -> 0x0680 NV097_SET_COMPOSITE_MATRIX[0] 0x43d0841d
_PGRAPH_METHOD_RE = re.compile(
    r"nv2a_pgraph_method\s+" + _SUBCHANNEL + r":\s+" + _CLASS + r"\s+->\s+" + _OP + r"\s+" + _OPNAME + _PARAM
)

NV2A_CLASS_3D = 0x97
NV097_SET_TRANSFORM_PROGRAM_START = 0x1EA0
NV097_SET_TRANSFORM_PROGRAM_RANGE_BASE = 0x0B00
NV097_SET_TRANSFORM_PROGRAM_RANGE_END = 0x0B7C


def sanitize_pgraph_transform_program(content: str) -> str | None:
    shader_program: list[int] = []
    for line in content.split():
        match = _PGRAPH_METHOD_RE.match(line)
        if match:
            nv_class = int(match.group(2), 16)
            if nv_class != NV2A_CLASS_3D:
                continue
            nv_op = int(match.group(3), 16)
            nv_param = int(match.group(4), 16)

            is_vertex_shader_upload = (
                nv_op >= NV097_SET_TRANSFORM_PROGRAM_RANGE_BASE and nv_op <= NV097_SET_TRANSFORM_PROGRAM_RANGE_END
            )
            if is_vertex_shader_upload:
                shader_program.append(nv_param)
            elif shader_program:
                break

    if shader_program:
        num_values = len(shader_program)

        # Split the 16-byte instructions into sublists.
        if (num_values % 4) != 0:
            msg = f"Invalid input, {num_values} is not divisible by 4."
            raise ValueError(msg)

        opcodes = [shader_program[start : start + 4] for start in range(0, num_values, 4)]
        return "\n".join(nv2a_vsh.disassemble.disassemble(opcodes, explain=False))

    return None


def sanitize_vsh_source(source_code: str) -> str:
    """Attempts to extract vsh code from various formats."""

    if "/* Slot " in source_code:
        result = sanitize_xemu_glsl(source_code)
        if result:
            return result

    result = sanitize_pgraph_transform_program(source_code)
    if result:
        return result

    return source_code
