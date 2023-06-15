"""Provides functionality to browse the end state of the shader."""

from typing import Callable
from typing import List
from typing import Optional

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.app import Binding
from textual.app import ComposeResult
from textual.css import query
from textual.containers import VerticalScroll
from textual.widgets import ContentSwitcher
from textual.widgets import Static

from nv2adbg._error_message import _CenteredErrorMessage
from nv2adbg._register_view import layout_register_lines
from nv2adbg.simulator import Context
from nv2adbg.simulator import Register

_OUTPUT_REGISTER_TO_FRIENDLY_NAME = {
    "o0": "oPos",
    "o3": "oD0",
    "o4": "oD1",
    "o5": "oFog",
    "o6": "oPts",
    "o7": "oB0",
    "o8": "oB1",
    "o9": "oT0",
    "o10": "oT1",
    "o11": "oT2",
    "o12": "oT3",
}


class _RegisterSetPanel(Static):
    COMPONENT_CLASSES = {
        "registersetpanel--register",
        "registersetpanel--value",
    }

    DEFAULT_CSS = """
    _RegisterSetPanel .registersetpanel--register {
        background: $surface;
        color: $text;
    }
    _RegisterSetPanel .registersetpanel--value {
        background: $surface;
        color: $text;
    }
    """

    def __init__(self, title: str):
        super().__init__()
        self._title = title
        self._registers = None
        self._name_modifier = None

    def set_registers(
        self,
        registers: List[Register],
        name_modifier: Optional[Callable[[str], str]] = None,
    ):
        self._registers = registers
        self._name_modifier = name_modifier

    def render(self) -> RenderableType:
        register_lines = [self._build_renderables(r) for r in self._registers]
        if not register_lines:
            return ""
        content = layout_register_lines(register_lines, self.size.width)
        return Panel(content, title=self._title)

    def _build_renderables(self, register: Register) -> List[Text]:
        ret = [
            Text.assemble(
                (
                    self._name_modifier(register.name)
                    if self._name_modifier
                    else register.name,
                    self.get_component_rich_style("registersetpanel--register"),
                )
            )
        ]

        value_style = self.get_component_rich_style("registersetpanel--value")
        ret.append(Text(f" {register.x}", value_style))
        ret.append(Text(f" {register.y}", value_style))
        ret.append(Text(f" {register.z}", value_style))
        ret.append(Text(f" {register.w}", value_style))

        return ret


class _ProgramOutputsViewer(Static):
    """Provides a browsing interface to view the final state of registers."""

    DEFAULT_CSS = """
    _ProgramOutputsViewer {
        height: 1fr;
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Cursor up", show=False),
        Binding("down", "cursor_down", "Cursor down", show=False),
        Binding("pageup", "cursor_pageup", "Cursor pageup", show=False),
        Binding("pagedown", "cursor_pagedown", "Cursor pagedown", show=False),
        Binding("home", "cursor_home", "Cursor home", show=False),
        Binding("end", "cursor_end", "Cursor end", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.can_focus = True
        self._input_context: Optional[Context] = None
        self._output_context: Optional[Context] = None

        self._scroll_area = VerticalScroll(id="content")
        self._outputs_panel = _RegisterSetPanel("Outputs")
        self._constants_panel = _RegisterSetPanel("Constants")
        self._temps_panel = _RegisterSetPanel("Temp registers")
        self._address_panel = _RegisterSetPanel("Address")

    def set_context(self, input_context: Context, output_context: Context):
        self._input_context = input_context
        self._output_context = output_context

        def rename_output_register(name: str) -> str:
            return _OUTPUT_REGISTER_TO_FRIENDLY_NAME.get(name, name)

        self._outputs_panel.set_registers(
            output_context.outputs, rename_output_register
        )

        constants = _filter_unchanged(
            self._input_context.constants, self._output_context.constants
        )

        def rename_constant_register(name: str) -> str:
            return f"c[{name[1:]}]"

        self._constants_panel.set_registers(constants, rename_constant_register)
        self._constants_panel.display = bool(constants)

        temps = _filter_unchanged(self._input_context.temps, self._output_context.temps)
        self._temps_panel.set_registers(temps)
        self._temps_panel.display = bool(temps)

        self._address_panel.set_registers([output_context.address])
        try:
            self.query_one(ContentSwitcher).current = self._activeContentId
        except query.NoMatches:
            # Ignore context being set prior to composition.
            pass

        self.update()

    @property
    def _activeContentId(self) -> str:
        if not self._input_context:
            return "no-input-context"

        if not self._output_context:
            return "no-output-context"
        return "content"

    def compose(self) -> ComposeResult:

        with ContentSwitcher(initial=self._activeContentId):
            yield _CenteredErrorMessage(
                "No input context available, load data via the File menu.",
                id="no-input-context",
            )

            yield _CenteredErrorMessage(
                "No output context available, simulation failed.",
                id="no-output-context",
            )

            with self._scroll_area:
                yield self._outputs_panel
                yield self._constants_panel
                yield self._temps_panel
                yield self._address_panel

    def _action_cursor_up(self):
        self._scroll_area.scroll_up()

    def _action_cursor_down(self):
        self._scroll_area.scroll_down()

    def _action_cursor_pageup(self):
        self._scroll_area.scroll_page_up()

    def _action_cursor_pagedown(self):
        self._scroll_area.scroll_page_down()

    def _action_cursor_home(self):
        self._scroll_area.scroll_home()

    def _action_cursor_end(self):
        self._scroll_area.scroll_end()


def _filter_unchanged(old: List[Register], new: List[Register]) -> List[Register]:
    old_by_register_name = {x.name: x for x in old}
    return [x for x in new if x != old_by_register_name[x.name]]
