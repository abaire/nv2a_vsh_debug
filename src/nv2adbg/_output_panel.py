"""Provides a widget to render simulator.Step outputs."""

from typing import List
from typing import Optional

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

    COMPONENT_CLASSES = {
        "outputpanel--register",
        "outputpanel--register-unused",
        "outputpanel--value",
        "outputpanel--value-unused",
    }

    DEFAULT_CSS = """
    _OutputPanel .outputpanel--register {
        color: $text;
        text-style: bold;
    }
    _OutputPanel .outputpanel--register-unused {
        color: $text;
    }
    _OutputPanel .outputpanel--value {
        color: $success;
        text-style: bold;
    }
    _OutputPanel .outputpanel--value-unused {
        color: $error;
    }
    """

    def __init__(self):
        super().__init__()

        self._step: Optional[Step] = None

    def on_mount(self) -> None:
        self._register_style = self.get_component_rich_style("outputpanel--register")
        self._muted_register_style = self.get_component_rich_style(
            "outputpanel--register-unused"
        )
        self._value_style = self.get_component_rich_style("outputpanel--value")
        self._muted_value_style = self.get_component_rich_style(
            "outputpanel--value-unused"
        )

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
            stages = ""
        else:
            stages = Table.grid(expand=True)
            stages.add_column(ratio=1)
            stages.add_column(ratio=1)

            outputs = self._step.outputs
            stages.add_row(
                *[
                    self._render_register_values(stage, outputs[stage])
                    for stage in sorted(outputs.keys(), reverse=True)
                ]
            )

        layout = Layout()
        layout.split_column(
            Rule("Outputs"),
            Layout(stages),
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

        state = self._step.state

        for register in registers:
            elements = [(register.raw_name, self._register_style)]
            if register.sorted_mask != "xyzw":
                elements.append((".", self._muted_register_style))
                elements.append((register.sorted_mask, self._register_style))
            row = [Text.assemble(*elements)]

            def get_value_style(component: str) -> Style:
                return (
                    self._value_style
                    if component in register.sorted_mask
                    else self._muted_value_style
                )

            x, y, z, w = state.get(f"{register.canonical_name}")
            row.append(Text(f" {x}", style=get_value_style("x")))
            row.append(Text(f" {y}", style=get_value_style("y")))
            row.append(Text(f" {z}", style=get_value_style("z")))
            row.append(Text(f" {w}", style=get_value_style("w")))

            inner.add_row(*row)

        outer.add_row(Text.assemble((stage_name, "underline"), (": ", "")), inner)
        return outer
