from typing import List, Optional

from _nv2a_vsh_cpu import ffi
from _nv2a_vsh_cpu import lib

_OPCODES = [
    "NOP",
    "MOV",
    "MUL",
    "ADD",
    "MAD",
    "DP3",
    "DPH",
    "DP4",
    "DST",
    "MIN",
    "MAX",
    "SLT",
    "SGE",
    "ARL",
    "RCP",
    "RCC",
    "RSQ",
    "EXP",
    "LOG",
    "LIT",
]

_REGISTERS = [
    "__UNUSED__",
    "R",
    "v",
    "o",
    "c",
    "A",
]

_WRITEMASKS = [
    "",
    ".w",
    ".z",
    ".zw",
    ".y",
    ".yw",
    ".yz",
    ".yzw",
    ".x",
    ".xw",
    ".xz",
    ".xzw",
    ".xy",
    ".xyw",
    ".xyz",
    "",  # ".xyzw",
]

_OUTPUT_NAMES = {
    0: "oPos",
    3: "oD0",
    4: "oD1",
    5: "oFog",
    6: "oPts",
    7: "oB0",
    8: "oB1",
    9: "oT0",
    10: "oT1",
    11: "oT2",
    12: "oT3",
}

_SWIZZLES = "xyzw"


def _stringify_output(type, index, writemask) -> str:
    mask = _WRITEMASKS[writemask]

    if type == lib.NV2ART_CONTEXT:
        return f"c[{index}]{mask}"

    if type == lib.NV2ART_OUTPUT:
        return f"{_OUTPUT_NAMES[index]}{mask}"

    return f"{_REGISTERS[type]}{index}{mask}"


def _make_swizzle(components: List[int]) -> str:
    if components == [0, 1, 2, 3]:
        return ""

    components.reverse()
    while len(components) > 1 and components[0] == components[1]:
        components = components[1:]
    components.reverse()

    components = [_SWIZZLES[val] for val in components]
    swizzle_str = "".join(components)
    return f".{swizzle_str}"


def _stringify_input(type, index, swizzle, negate: bool, relative: bool) -> str:

    if type == lib.NV2ART_CONTEXT:
        rel = "A0+" if relative else ""
        reg = f"c[{rel}{index}]"
    else:
        reg = _REGISTERS[type] + str(index)

    # Expand the FFI array into a list for easier manipulation.
    swizzle_str = _make_swizzle([val for val in swizzle])

    neg = "-" if negate else ""
    return f"{neg}{reg}{swizzle_str}"


def _stringify_op(operation) -> str:
    info = _operation_to_dict(operation)
    opcode = info["mnemonic"]
    input_str = ", ".join(info["inputs"])
    outputs = info["outputs"]

    ret = []
    for output in outputs:
        operation = f"{opcode} {output}, {input_str}"
        ret.append(operation)
    return " + ".join(ret)


def _operation_to_dict(operation) -> dict:
    outputs = []
    for i in range(2):
        out = operation.outputs[i]
        if out.type == lib.NV2ART_NONE:
            break
        outputs.append(_stringify_output(out.type, out.index, out.writemask))

    inputs = []
    for i in range(3):
        input = operation.inputs[i]
        if input.type == lib.NV2ART_NONE:
            break

        type = input.type
        index = input.index
        swizzle = input.swizzle
        negate = input.is_negated != 0
        relative = input.is_relative != 0
        inputs.append(_stringify_input(type, index, swizzle, negate, relative))

    ret = {
        "mnemonic": _OPCODES[operation.opcode],
        "inputs": inputs,
        "outputs": outputs,
    }
    return ret


class Nv2aVshStep:
    def __init__(self, token: List[int]):
        self._step = ffi.new("Nv2aVshStep *")
        result = lib.nv2a_vsh_parse_step(self._step, token)
        if result != lib.NV2AVPR_SUCCESS:
            raise Exception(f"Failed to parse nv2a token {token}")

    def source(self) -> str:
        ret = []
        if self._step.mac.opcode:
            ret.append(_stringify_op(self._step.mac))
        if self._step.ilu.opcode:
            ret.append(_stringify_op(self._step.ilu))

        return " + ".join(ret)

    def get(self, mac_or_ilu) -> Optional[dict]:
        """Returns a dictionary with the mnemonic, outputs, and inputs of the mac or ilu portion of this step."""
        if mac_or_ilu == "mac":
            return self._get_mac_dict()
        if mac_or_ilu == "ilu":
            return self._get_ilu_dict()

        raise Exception(f"Unexpected get field {mac_or_ilu}")

    def _get_mac_dict(self) -> Optional[dict]:
        if not self._step.mac.opcode:
            return None
        return _operation_to_dict(self._step.mac)

    def _get_ilu_dict(self) -> Optional[dict]:
        if not self._step.ilu.opcode:
            return None
        return _operation_to_dict(self._step.ilu)


class Nv2aVshEmuState:
    def __init__(self):
        self._state = ffi.new("Nv2aVshCPUFullExecutionState*")
        self._token = lib.nv2a_vsh_emu_initialize_full_execution_state(self._state)

    def set_state(
        self, input: List, context: List, temp: List, output: List, address: List
    ):
        def _set(destination, register):
            name, x, y, z, w = register
            index = int(name[1:]) * 4
            destination[index] = x
            destination[index + 1] = y
            destination[index + 2] = z
            destination[index + 3] = w

        for register in input:
            _set(self._state.input_regs, register)
        for register in context:
            _set(self._state.context_regs, register)
        for register in temp:
            _set(self._state.temp_regs, register)
        for register in output:
            _set(self._state.output_regs, register)

        if address:
            self._state.address_reg[0] = address[0]
            self._state.address_reg[1] = address[1]
            self._state.address_reg[2] = address[2]
            self._state.address_reg[3] = address[3]

    def to_dict(self, inputs_only: bool):
        """Returns a dictionary representation of this state."""

        def retrieve_regs(prefix: str, source, count: int) -> List:
            regs = []
            for i in range(count):
                register = [f"{prefix}{i}"]
                offset = i * 4
                for component in range(4):
                    register.append(source[offset + component])
                regs.append(register)
            return regs

        ret = {
            "input": retrieve_regs("v", self._state.input_regs, 16),
            "constant": retrieve_regs("c", self._state.context_regs, 192),
        }

        if not inputs_only:
            ret["address"] = retrieve_regs("", self._state.address_reg, 1)[0][1:]
            ret["temp"] = retrieve_regs("R", self._state.temp_regs, 12)
            ret["output"] = retrieve_regs("o", self._state.output_regs, 13)

        return ret

    def apply(self, step: Nv2aVshStep):
        lib.nv2a_vsh_emu_apply(ffi.addressof(self._token), step._step)
