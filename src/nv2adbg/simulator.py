"""Provides functions to simulate the behavior of an original xbox nv2a vertex shader."""

import collections
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import replace
from typing import Dict
from typing import FrozenSet
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple
from typing_extensions import Self

import nv2avsh
from nv2adbg.py_nv2a_vsh_emu import Nv2aVshEmuState
from nv2adbg.py_nv2a_vsh_emu import Nv2aVshStep

OUTPUT_TO_INDEX = {
    "oPos": 0,
    "oD0": 3,
    "oD1": 4,
    "oFog": 5,
    "oPts": 6,
    "oB0": 7,
    "oB1": 8,
    "oT0": 9,
    "oT1": 10,
    "oT2": 11,
    "oT3": 12,
}


@dataclass(unsafe_hash=True)
class Register:
    """Holds the state of a single nv2a register."""

    name: str
    x: float = 0
    y: float = 0
    z: float = 0
    w: float = 0

    def to_json(self) -> List:
        return [self.name, self.x, self.y, self.z, self.w]

    def get(self, mask: str) -> List[float]:
        ret = []
        for field in mask:
            if field == "x":
                ret.append(self.x)
            elif field == "y":
                ret.append(self.y)
            elif field == "z":
                ret.append(self.z)
            elif field == "w":
                ret.append(self.w)
            else:
                raise Exception(f"Invalid mask component {field}")
        return ret

    def set(self, mask: str, value: Tuple[float, float, float, float]):
        for field in mask:
            if field == "x":
                self.x = value[0]
            elif field == "y":
                self.y = value[1]
            elif field == "z":
                self.z = value[2]
            elif field == "w":
                self.w = value[3]
            else:
                raise Exception(f"Invalid mask component {field}")

    def __str__(self):
        return f"{self.name}[{self.x:f},{self.y:f},{self.z:f},{self.w:f}]"


def canonicalize_register_name(name: str) -> str:
    """Converts sugared register names to canonical ones. E.g., c[123] => c123, oPos => o0."""

    # Remap the R12 -> oPos alias.
    if name == "R12":
        return "o0"

    # c[X] => cX
    ret = name.replace("[", "").replace("]", "")

    # Symbolic output registers => oX
    output_index = OUTPUT_TO_INDEX.get(ret)
    if output_index is not None:
        return f"o{output_index}"

    return ret


@dataclass(unsafe_hash=True)
class RegisterReference:
    """Models a source reference to a single register which may include optional sign and mask components.

    Attributes:
            negate: bool - Whether the value of the register should be negated.
            raw_name: str - The name of the register as defined in source code.
            canonical_name: str - The name of the register without optional brackets (e.g., c[120] => c120, oD0 => o3).
            mask: str - The raw component mask to be applied when accessing the register.
            extended_mask: str - The mask padded to be exactly 4 elements long by duplicating the last component.
                                 E.g., "xyz" => "xyzz", "y" => "yyyy".
            sorted_mask: str - The mask elements deduplicated and sorted to canonical order (x, y, z, w).
    """

    negate: Optional[bool]
    raw_name: str
    canonical_name: str
    mask: str
    sorted_mask: str
    extended_mask: Optional[str]

    @classmethod
    def from_source(cls, source: str) -> Self:

        if source[0] == "-":
            negate = True
            source = source[1:]
        else:
            negate = False

        components = source.split(".")

        raw_name = components[0]
        canonical_name = canonicalize_register_name(raw_name)

        if len(components) == 1:
            mask = "xyzw"
            sorted_mask = mask
        else:
            mask = components[1]
            sorted_mask = "".join(sorted(set(mask)))
            if sorted_mask[0] == "w":
                sorted_mask = f"{sorted_mask[1:]}w"

        extended_mask = mask
        while len(extended_mask) < 4:
            extended_mask += extended_mask[-1]

        return cls(
            negate=negate,
            raw_name=raw_name,
            canonical_name=canonical_name,
            mask=mask,
            sorted_mask=sorted_mask,
            extended_mask=extended_mask,
        )

    def destructively_satisfy(self, other: Self) -> str:
        """Returns the intersected mask between `self` and `other`, clearing any mask components that overlap.

        This destructively mutates this RegisterReference, clearing the negate and extended_mask fields and sorting the
        mask field. This is only meant to be used during ancestor tracking where the original RegisterReference's are
        preserved elsewhere.

        The return value is the sorted intersection between the self and other masks. E.g., if self = R0.xyz and
        other = R0.xzw, the return would be "xz".
        """
        if other.canonical_name != self.canonical_name:
            return ""

        mask_intersection = set(self.mask) & set(other.mask)
        if not mask_intersection:
            return ""

        self.negate = None
        self.extended_mask = None
        self.mask = "".join(sorted(set(self.mask) - mask_intersection))
        return "".join(sorted(mask_intersection))

    def lossy_merge(self, other: Self) -> Self:
        """Returns a new RegisterReference combining this RegisterReference with the mask another RegisterReference.

        This merge loses some information, so negate and extended_mask are cleared and mask is sorted in the new copy.
        """
        if other.canonical_name != self.canonical_name or other == self:
            return replace(self)

        merged_mask = "".join(sorted(set(self.mask) | set(other.mask)))
        return replace(
            self,
            negate=None,
            extended_mask=None,
            mask=merged_mask,
            sorted_mask=merged_mask,
        )


class Context:
    """Holds the current register context."""

    def __init__(self):
        self._state = Nv2aVshEmuState()

        self._inputs = []
        self._constants = []
        self._address = None
        self._temps = []
        self._outputs = []
        self._update()

    def from_dict(self, registers: dict):
        """Populates this context from the given dictionary of register states."""

        inputs = registers.get("input", [])
        constants = registers.get("constant", [])
        temps = registers.get("temp", [])
        outputs = registers.get("output", [])
        address = registers.get("address", [])

        self._state.set_state(inputs, constants, temps, outputs, address)
        self._update()

    def to_dict(self, inputs_only: bool = False):
        """Returns a dictionary representation of this context."""
        return self._state.to_dict(inputs_only)

    def apply(self, step):
        self._state.apply(step)
        self._update()

    def duplicate(self):
        new = Context()
        new.from_dict(self.to_dict())
        return new

    def _get_reg_and_mask(
        self, reg_ref: RegisterReference, extend: bool = False
    ) -> Tuple[Register, str]:
        reg = Register(
            reg_ref.raw_name, *self._state.get_register_value(reg_ref.canonical_name)
        )

        if extend:
            return reg, reg_ref.extended_mask
        return reg, reg_ref.mask

    def get(self, source: str) -> Tuple[float, float, float, float]:
        register_ref = RegisterReference.from_source(source)
        reg, mask = self._get_reg_and_mask(register_ref, True)

        ret = reg.get(mask)
        if register_ref.negate:
            ret = [-1 * val for val in ret]
        return ret[0], ret[1], ret[2], ret[3]

    def set(self, target: str, value: Tuple[float, float, float, float]):
        register_ref = RegisterReference.from_source(target)
        reg, mask = self._get_reg_and_mask(register_ref)
        reg.set(mask, value)
        self._update()

    def _update(self):
        def convert_register_list(lst: List) -> List[Register]:
            return [Register(*x) for x in lst]

        vals = self.to_dict()
        self._inputs = convert_register_list(vals["input"])
        self._constants = convert_register_list(vals["constant"])
        self._address = Register("A0", *vals["address"])
        self._temps = convert_register_list(vals["temp"])
        self._outputs = convert_register_list(vals["output"])

    @property
    def inputs(self) -> List[Register]:
        return self._inputs

    @property
    def constants(self) -> List[Register]:
        return self._constants

    @property
    def address(self) -> Register:
        return self._address

    @property
    def temps(self) -> List[Register]:
        return self._temps

    @property
    def outputs(self) -> List[Register]:
        return self._outputs


class Step:
    """Models a single step in a Shader Trace."""

    def __init__(
        self, index: int, source: str, state: Context, instruction: Nv2aVshStep
    ):
        self._index = index
        self._source = source
        self._state = state
        self._instruction = instruction

        self._inputs: Dict[str, List[RegisterReference]] = _extract_inputs(instruction)
        self._outputs: Dict[str, List[RegisterReference]] = _extract_outputs(
            instruction
        )

        self._ancestors: Optional[
            Dict[str, Tuple[List["Ancestor"], Set[RegisterReference]]]
        ] = None

    def to_dict(self) -> dict:
        """Returns a dictionary representation of this Step."""
        return {
            "source": self._source,
            "state": self._state.to_dict(),
            "instruction": {
                "mac": self._instruction.get("mac"),
                "ilu": self._instruction.get("ilu"),
            },
        }

    @property
    def index(self) -> int:
        """The numerical index of this Step in the context of the containing Trace."""
        return self._index

    @property
    def source(self) -> str:
        return self._source

    @property
    def state(self) -> Context:
        return self._state

    @property
    def ancestors(
        self,
    ) -> Optional[Dict[str, Tuple[List["Ancestor"], Set[RegisterReference]]]]:
        """Returns information about previous Steps that have directly contributed to inputs of this Step.

        The returned dictionary contains entries for the "mac" and/or "ilu" stage of this Step. The associated value is
        a tuple containing a list of Ancestor links pointing to the mac/ilu stage of some previous Step and a set of
        RegisterReferences containing registers and masks that were not satisfied by any known previous step (generally
        these should be input registers or constant registers)."""
        return self._ancestors

    def get_ancestors_for_stage(
        self, mac_or_ilu: str
    ) -> Tuple[List["Ancestor"], Set[RegisterReference]]:
        return self._ancestors.get(mac_or_ilu, ([], set()))

    def _set_ancestors(
        self, val: Optional[Dict[str, Tuple[List["Ancestor"], Set[RegisterReference]]]]
    ) -> None:
        self._ancestors = val

    def has_stage(self, mac_or_ilu: str) -> bool:
        """Returns true if this step has an operation for the given stage ("mac" or "ilu")."""
        return self._instruction.get(mac_or_ilu) is not None

    @property
    def inputs(self) -> Dict[str, List[RegisterReference]]:
        return self._inputs

    @property
    def joined_inputs(self) -> List[RegisterReference]:
        """Returns the combined inputs used by the MAC and ILU portions of this Step."""
        ret = []
        for refs in self._inputs.values():
            ret.extend(refs)
        return ret

    @property
    def outputs(self) -> Dict[str, List[RegisterReference]]:
        return self._outputs

    @property
    def joined_outputs(self) -> List[RegisterReference]:
        """Returns the combined outputs from the MAC and ILU portions of this Step."""
        ret = []
        for refs in self._outputs.values():
            ret.extend(refs)
        return ret


@dataclass(unsafe_hash=True, frozen=True)
class Ancestor:
    """Captures a relationship in which the mac|ilu of the given Step contributes to the input of some other Step.

    step: The Step contributing to some other Step's input.
    mac_or_ilu: Whether it is the Step's mac or ilu stage that contributes the value.
    components: Dictionary mapping output registers to the components of the output that are used.
    """

    step: Step
    mac_or_ilu: str
    components: FrozenSet[Tuple[str, str]]


class Trace:
    """Provides verbose information about each step in a shader program."""

    def __init__(
        self, input_context: Context, steps: List[Step], output_context: Context
    ):
        self._input_context = input_context
        self._steps = steps
        self._output_context = output_context

    def to_dict(self):
        """Returns a dictionary representation of this Trace."""
        return {
            "input": self._input_context.to_dict(),
            "steps": [step.to_dict() for step in self._steps],
            "output": self._output_context.to_dict(),
        }

    @property
    def input_context(self) -> Context:
        return self._input_context

    @property
    def inputs(self) -> dict:
        return self._input_context.to_dict()

    @property
    def steps(self):
        return self._steps

    @property
    def output_context(self) -> Context:
        return self._output_context

    @property
    def output(self):
        return self._output_context.to_dict()


class Shader:
    """Models an nv2a vertex shader."""

    def __init__(self):
        self._reformatted_source = []
        self._instructions = []
        self._input_context = Context()

    def set_source(self, source_code: str) -> List[str]:
        """Sets the source code for this shader."""
        machine_code, errors = nv2avsh.assemble.assemble(source_code)
        if errors:
            return [f"{error.line}:{error.column}: {error.message}" for error in errors]
        self._instructions = [Nv2aVshStep(token) for token in machine_code]
        self._reformatted_source = [ins.source() for ins in self._instructions]
        return []

    def set_initial_state(self, state: dict):
        """Sets the initial register state for this shader."""
        ctx = Context()
        ctx.from_dict(state)
        self._input_context = ctx

    def merge_initial_state(self, state: dict):
        """Merges values from the given dictionary into the current initial context."""
        self._input_context.from_dict(state)

    @property
    def initial_state(self) -> Context:
        return self._input_context

    def _apply(self, instruction, input: Context) -> Context:
        output = input.duplicate()
        output.apply(instruction)
        return output

    def _simulate(self) -> Tuple[List[Tuple[str, Context, Nv2aVshStep]], Context]:
        active_state = self._input_context
        states = []
        for line, instruction in zip(self._reformatted_source, self._instructions):
            active_state = self._apply(instruction, active_state)
            states.append((line, active_state, instruction))

        return states, active_state

    def explain(self, process_ancestors: bool = True) -> Trace:
        """Returns a Trace providing details about the execution state of this shader."""
        steps, output = self._simulate()
        step_objects = []
        for idx, (source, step_output, instruction) in enumerate(steps):
            new_step = Step(idx, source, step_output, instruction)
            if process_ancestors:
                ancestors = _find_ancestors(new_step, step_objects)
                new_step._set_ancestors(ancestors)

            step_objects.append(new_step)

        return Trace(self._input_context, step_objects, output)


def _find_ancestors(
    new_step: Step,
    previous_steps: List[Step],
) -> Dict[str, Tuple[List[Ancestor], Set[RegisterReference]]]:
    """Attempts to find contributors to the inputs of the given `new_step`

    Returns a dict of mac|ilu to a list of Ancestor instances that contribute to the mac|ilu of `new_step` and a Set of
    RegisterReferences that are unsatisfied.
    """

    inputs = deepcopy(new_step.inputs)
    previous_steps = reversed(previous_steps)

    def find_dependent_components(
        input: RegisterReference, outputs: List[RegisterReference]
    ) -> dict[str, str]:
        """Removes overlapping masks between the given outputs and input, returning satisfied components.

        E.g., if input is R0.xyw, R1 and outputs is R0.x, R1 the returned dict will be { "R0": "x", "R1": "xyzw" }
        """

        ret = {}
        for out_ref in outputs:
            dependent_components = input.destructively_satisfy(out_ref)
            if not dependent_components:
                continue

            ret[out_ref.canonical_name] = dependent_components
            if not input.mask:
                break

        return ret

    def clean_satisfied_inputs():
        keys = list(inputs.keys())
        for key in keys:
            inputs[key] = list(filter(lambda x: x.mask, inputs[key]))
            if not inputs[key]:
                del inputs[key]

    ancestors = collections.defaultdict(list)

    for prev in previous_steps:
        prev_outputs = prev.outputs

        for in_key, in_refs in inputs.items():
            for in_ref in in_refs:
                if not in_ref.mask:
                    continue

                for out_key, out_refs in prev_outputs.items():
                    components = find_dependent_components(in_ref, out_refs)
                    if components:
                        ancestor = Ancestor(
                            prev, out_key, frozenset(components.items())
                        )
                        if ancestor not in ancestors[in_key]:
                            ancestors[in_key].append(ancestor)

        clean_satisfied_inputs()
        if not inputs:
            break

    # Return a map of mac|ilu to ([Ancestors], {RegisterRefs (unsatisfied)})
    ret = {}
    for in_key in new_step.inputs.keys():
        ret[in_key] = (
            ancestors.get(in_key, []),
            set(inputs.get(in_key, [])),
        )

    return ret


def _extract_inputs(ins: Nv2aVshStep) -> Dict[str, List[RegisterReference]]:
    """Returns a dictionary mapping mac|ilu to registers referenced as inputs to the instruction."""
    return _extract_register_references(ins, "inputs")


def _extract_outputs(ins: Nv2aVshStep) -> Dict[str, List[RegisterReference]]:
    """Returns a dictionary mapping mac|ilu to registers referenced as outputs of the instruction."""
    return _extract_register_references(ins, "outputs")


def _extract_register_references(
    ins: Nv2aVshStep, key: str
) -> Dict[str, List[RegisterReference]]:
    """Returns a dict mapping mac and/or ilu to a dict mapping register name to Set[mask] for the given key."""
    ret = collections.defaultdict(list)

    def process_instruction(mac_or_ilu: str):
        map = ins.get(mac_or_ilu)
        if not map:
            return

        for element in map[key]:
            ret[mac_or_ilu].append(RegisterReference.from_source(element))

    process_instruction("mac")
    process_instruction("ilu")

    return ret
