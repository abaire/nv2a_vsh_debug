"""Provides a widget to render simulator.Step outputs."""

from typing import List

from rich.columns import Columns
from rich.console import RenderableType
from rich.layout import Layout
from rich.rule import Rule
from rich.style import Style
from rich.text import Text
from textual.geometry import Size
from textual.widgets import Static

from nv2adbg.simulator import RegisterReference
from nv2adbg.simulator import Step


class _OutputPanel(Static):
    """Renders outputs for a single step in the shader."""

    def set_step(self, step: Step):
        self._step = step
        self.update()

    def get_content_height(self, container: Size, viewport: Size, width: int) -> int:
        return 2

    def render(self) -> RenderableType:
        if not self._step:
            composables = [""]
        else:
            outputs = self._step.outputs
            composables = [
                self._render_output(stage, outputs[stage])
                for stage in sorted(outputs.keys(), reverse=True)
            ]

        layout = Layout(size=2, ratio=0)
        layout.split_column(
            Rule("Outputs"),
            Layout(
                Columns(
                    composables,
                    expand=True,
                ),
                size=1,
            ),
        )
        return layout

    def _render_output(
        self, stage_name: str, registers: List[RegisterReference]
    ) -> RenderableType:
        elements = [(f"{stage_name}: ", "bold")]

        theme = self.app.get_css_variables()
        muted_suffix = "darken-2" if self.app.dark else "lighten-1"
        register_style = Style.parse(theme.get("success"))
        muted_register_style = Style.parse(theme.get(f"success-{muted_suffix}"))
        value_style = Style.parse(theme.get("success"))
        muted_value_style = Style.parse(theme.get(f"success-{muted_suffix}"))

        state = self._step.state

        for register in registers:
            elements.append((register.raw_name, register_style))
            if register.sorted_mask != "xyzw":
                elements.append((".", muted_register_style))
                elements.append((register.sorted_mask, register_style))

            def get_value_style(component: str) -> Style:
                return (
                    value_style
                    if component in register.sorted_mask
                    else muted_value_style
                )

            x, y, z, w = state.get(f"{register.canonical_name}")
            elements.append((f" {x}", get_value_style("x")))
            elements.append((f", ", muted_value_style))
            elements.append((f" {y}", get_value_style("y")))
            elements.append((f", ", muted_value_style))
            elements.append((f" {z}", get_value_style("z")))
            elements.append((f", ", muted_value_style))
            elements.append((f" {w}", get_value_style("w")))

        return Text.assemble(*elements)
