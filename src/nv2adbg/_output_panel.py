"""Provides a widget to render simulator.Step outputs."""

from typing import List

from rich.columns import Columns
from rich.console import RenderableType
from rich.layout import Layout
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
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
        if not self._step:
            return 2

        ret = 0
        for outputs in self._step.outputs.values():
            ret = max(ret, len(outputs))
        return 1 + ret

    def render(self) -> RenderableType:
        if not self._step:
            composables = [""]
        else:
            outputs = self._step.outputs
            composables = [
                self._render_register_values(stage, outputs[stage])
                for stage in sorted(outputs.keys(), reverse=True)
            ]

        layout = Layout()
        layout.split_column(
            Rule("Outputs"),
            Layout(
                Columns(
                    composables,
                    expand=True,
                ),
            ),
        )
        return layout

    def _render_register_values(
        self, stage_name: str, registers: List[RegisterReference]
    ) -> RenderableType:
        outer = Table.grid()
        outer.add_column()
        outer.add_column()

        inner = Table.grid()
        inner.add_column()
        inner.add_column()
        inner.add_column()
        inner.add_column()
        inner.add_column()

        theme = self.app.get_css_variables()
        muted_suffix = "darken-2" if self.app.dark else "lighten-1"
        register_style = Style.parse(theme.get("success"))
        muted_register_style = Style.parse(theme.get(f"success-{muted_suffix}"))
        value_style = Style.parse(theme.get("success"))
        muted_value_style = Style.parse(theme.get(f"success-{muted_suffix}"))

        state = self._step.state

        for register in registers:
            elements = [(register.raw_name, register_style)]
            if register.sorted_mask != "xyzw":
                elements.append((".", muted_register_style))
                elements.append((register.sorted_mask, register_style))
            row = [Text.assemble(*elements)]

            def get_value_style(component: str) -> Style:
                return (
                    value_style
                    if component in register.sorted_mask
                    else muted_value_style
                )

            x, y, z, w = state.get(f"{register.canonical_name}")
            row.append(Text(f" {x}", style=get_value_style("x")))
            row.append(Text(f" {y}", style=get_value_style("y")))
            row.append(Text(f" {z}", style=get_value_style("z")))
            row.append(Text(f" {w}", style=get_value_style("w")))

            inner.add_row(*row)

        outer.add_row(Text(f"{stage_name}: ", style="bold"), inner)
        return outer
