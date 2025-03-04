"""Provides a widget to render inputs to a simulator.Step."""

# ruff: noqa: RUF012 Mutable class attributes should be annotated with `typing.ClassVar`

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static

from nv2a_debug._register_view import layout_register_lines

if TYPE_CHECKING:
    from rich.console import RenderableType
    from rich.style import Style

    from nv2a_debug.simulator import RegisterReference, Step


class _InputPanel(Static):
    """Renders inputs for a single step in the shader."""

    COMPONENT_CLASSES = {
        "inputpanel--register",
        "inputpanel--register-unused",
        "inputpanel--value",
        "inputpanel--value-unused",
    }

    DEFAULT_CSS = """
    _InputPanel .inputpanel--register {
        color: $text;
        text-style: bold;
    }
    _InputPanel .inputpanel--register-unused {
        color: $text;
    }
    _InputPanel .inputpanel--value {
        color: $success;
        text-style: bold;
    }
    _InputPanel .inputpanel--value-unused {
        color: $error;
    }
    """

    def __init__(self) -> None:
        super().__init__()

        self._step: Step | None = None

    def on_mount(self) -> None:
        self._register_style = self.get_component_rich_style("inputpanel--register")
        self._muted_register_style = self.get_component_rich_style("inputpanel--register-unused")
        self._value_style = self.get_component_rich_style("inputpanel--value")
        self._muted_value_style = self.get_component_rich_style("inputpanel--value-unused")

    def set_step(self, step: Step):
        self._step = step
        self.update()

    def render(self) -> RenderableType:
        renderable: RenderableType
        if not self._step:
            renderable = ""
        else:
            inputs = self._step.inputs

            column_content_width = (self.size.width - 2) // len(inputs)
            if len(inputs) > 1:
                column_content_width -= 1

            renderable = Layout()
            stage_layouts = [
                self._render_input(stage, inputs[stage], column_content_width)
                for stage in sorted(inputs.keys(), reverse=True)
            ]

            if len(stage_layouts) > 1:
                # Insert a blank column between stages.
                spaced_layouts = [stage_layouts[0]]
                for layout in stage_layouts[1:]:
                    spaced_layouts.extend([Layout(" ", size=1), layout])
                stage_layouts = spaced_layouts

            renderable.split_row(*stage_layouts)

        return Panel(renderable, title="Inputs")

    def _render_input(self, stage_name: str, registers: list[RegisterReference], width: int) -> RenderableType:
        registers = _dedup_registers(registers)

        register_lines = [self._build_renderables(r) for r in registers]
        register_layout = layout_register_lines(register_lines, width)

        ret = Layout()
        ret.split_column(
            Layout(Text(stage_name, "underline"), size=1),
            register_layout,
        )
        return ret

    def _build_renderables(self, register: RegisterReference) -> list[Text]:
        ret = []

        elements = []
        elements.append((register.raw_name, self._register_style))
        if register.sorted_mask != "xyzw":
            elements.append((".", self._muted_register_style))
            elements.append((register.sorted_mask, self._register_style))
        ret.append(Text.assemble(*elements))

        def get_value_style(component: str) -> Style:
            return self._value_style if component in register.sorted_mask else self._muted_value_style

        if not self._step:
            msg = "_build_renderables called without self._step"
            raise ValueError(msg)

        state = self._step.input_state
        x, y, z, w = state.get(f"{register.canonical_name}")
        ret.append(Text(f" {x}", get_value_style("x")))
        ret.append(Text(f" {y}", get_value_style("y")))
        ret.append(Text(f" {z}", get_value_style("z")))
        ret.append(Text(f" {w}", get_value_style("w")))

        return ret


def _dedup_registers(registers: list[RegisterReference]) -> list[RegisterReference]:
    """Merges any duplicate references in the given register list."""
    ret = {registers[0].canonical_name: registers[0]}

    for ref in registers[1:]:
        existing = ret.get(ref.canonical_name)
        if not existing:
            ret[ref.canonical_name] = ref
            continue
        ret[ref.canonical_name] = existing.lossy_merge(ref)

    return [ret[x] for x in sorted(ret.keys())]
