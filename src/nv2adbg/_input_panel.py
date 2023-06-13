"""Provides a widget to render inputs to a simulator.Step."""

from typing import List
from typing import Optional

from rich.console import RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.style import Style
from rich.text import Text
from textual.widgets import Static

from nv2adbg._register_view import layout_register_lines
from nv2adbg.simulator import RegisterReference
from nv2adbg.simulator import Step


class _InputPanel(Static):
    """Renders inputs for a single step in the shader."""

    def __init__(self):
        super().__init__()

        self._step: Optional[Step] = None

    def set_step(self, step: Step):
        self._step = step
        self.update()

    def render(self) -> RenderableType:
        if not self._step:
            renderable = ""
        else:
            self._update_styled_colors()
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

    def _render_input(
        self, stage_name: str, registers: List[RegisterReference], width: int
    ) -> RenderableType:

        registers = _dedup_registers(registers)

        register_lines = [self._build_renderables(r) for r in registers]
        register_layout = layout_register_lines(register_lines, width)

        ret = Layout()
        ret.split_column(
            Layout(Text(stage_name, "bold"), size=1),
            register_layout,
        )
        return ret

    def _build_renderables(self, register: RegisterReference) -> List[Text]:
        ret = []

        elements = []
        elements.append((register.raw_name, self._register_style))
        if register.sorted_mask != "xyzw":
            elements.append((".", self._muted_register_style))
            elements.append((register.sorted_mask, self._register_style))
        ret.append(Text.assemble(*elements))

        def get_value_style(component: str) -> Style:
            return (
                self._value_style
                if component in register.sorted_mask
                else self._muted_value_style
            )

        state = self._step.state
        x, y, z, w = state.get(f"{register.canonical_name}")
        ret.append(Text(f" {x}", get_value_style("x")))
        ret.append(Text(f" {y}", get_value_style("y")))
        ret.append(Text(f" {z}", get_value_style("z")))
        ret.append(Text(f" {w}", get_value_style("w")))

        return ret

    def _update_styled_colors(self):
        theme = self.app.get_css_variables()
        muted_suffix = "darken-2" if self.app.dark else "lighten-1"

        self._register_style = Style.parse(theme.get("success"))
        self._muted_register_style = Style.parse(theme.get(f"success-{muted_suffix}"))
        self._value_style = Style.parse(theme.get("success"))
        self._muted_value_style = Style.parse(theme.get(f"success-{muted_suffix}"))


def _dedup_registers(registers: List[RegisterReference]) -> List[RegisterReference]:
    """Merges any duplicate references in the given register list."""
    ret = {registers[0].canonical_name: registers[0]}

    for ref in registers[1:]:
        existing = ret.get(ref.canonical_name)
        if not existing:
            ret[ref.canonical_name] = ref
            continue
        ret[ref.canonical_name] = existing.lossy_merge(ref)

    return [ret[x] for x in sorted(ret.keys())]
