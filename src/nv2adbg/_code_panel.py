"""Provides a widget to render and navigate nv2a vsh assembly code."""
from dataclasses import dataclass
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from rich.segment import Segment
from textual._cache import LRUCache
from textual.app import Binding
from textual.geometry import Region
from textual.geometry import Size
from textual.messages import Message
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Label

from nv2adbg import simulator


class _CodePanel(ScrollView, can_focus=True):
    """Renders the code view."""

    BINDINGS = [
        Binding("up", "cursor_up", "Cursor up", show=False),
        Binding("down", "cursor_down", "Cursor down", show=False),
        Binding("pageup", "cursor_pageup", "Cursor pageup", show=False),
        Binding("pagedown", "cursor_pagedown", "Cursor pagedown", show=False),
        Binding("home", "cursor_home", "Cursor home", show=False),
        Binding("end", "cursor_end", "Cursor end", show=False),
        ("a", "toggle_ancestors", "Show ancestors"),
    ]

    COMPONENT_CLASSES = {
        "codepanel--modifier",
        "codepanel--linenum",
        "codepanel--code",
        "codepanel--selected-modifier",
        "codepanel--selected-linenum",
        "codepanel--selected-code",
    }

    DEFAULT_CSS = """
    _CodePanel {
        height: 1fr;
        width: 1fr;
        overflow-y: scroll;
    }

    _CodePanel .codepanel--modifier {
        background: $surface;
        color: $text;
        width: 4;
    }
    _CodePanel .codepanel--linenum {
        background: $surface;
        color: $text;
    }
    _CodePanel .codepanel--code {
        background: $background;
        color: $text;
    }

    _CodePanel .codepanel--selected-modifier {
        background: $primary;
        color: $text;
        width: 4;
    }
    _CodePanel .codepanel--selected-linenum {
        background: $primary;
        color: $text;
    }
    _CodePanel .codepanel--selected-code {
        background: $primary;
        color: $text;
    }
    """

    cursor_pos = reactive(0, always_update=True)
    show_ancestors = reactive(False)

    class ActiveLineChanged(Message):
        """Sent when the current source line changes.

        Properties:
            linenum: int - The new line number.
            step: Optional[simulator.Step] - The Step at the new line.
        """

        def __init__(self, linenum: int, step: Optional[simulator.Step]) -> None:
            """linenum - The new line number."""
            super().__init__()
            self.linenum = linenum
            self.step = step

    @dataclass(unsafe_hash=True, frozen=True)
    class _LineCacheKey:
        """Key for the line cache used to reuse existing line Strips"""

        row: int
        width: int
        is_selected: bool
        modifiers: str

    def __init__(self):
        super().__init__()
        self._trace: Optional[simulator.Trace] = None
        self._lines: List[Tuple[str, str]] = []
        self._line_cache: LRUCache[_CodePanel._LineCacheKey, Strip] = LRUCache(512)
        self._start_line: int = 0

        # The root of the ancestor chain (the current cursor position in normal
        # mode, but may be locked to an arbitrary instruction). This is the
        # simulator.Step::index rather than a row index.
        self._ancestor_chain_root_step_index = None
        self._ancestor_locked = False
        self._highlighted_ancestors = set()
        self._highlighted_inputs = set()

    def set_shader_trace(self, trace: simulator.Trace):
        self._trace = trace

        self._lines.clear()
        self._start_line = 0
        self.cursor_pos = 0

        if not trace:
            self.virtual_size = Size(self.size.width, 0)
        else:
            linenum_width = len(str(len(self._trace.steps)))
            source_width = 0

            for idx, step in enumerate(self._trace.steps):
                source_width = max(source_width, len(step.source))

            for step in self._trace.steps:
                linenum = step.index + 1
                self._lines.append(
                    (
                        f"{linenum: >{linenum_width}}  ",
                        f"{step.source:{source_width}}",
                    )
                )

            self.virtual_size = Size(self.size.width, len(trace.steps))
            self.post_message(
                self.ActiveLineChanged(self.cursor_pos, self._trace.steps[0])
            )

    def notify_style_update(self) -> None:
        self._line_cache.clear()

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        line = self._render_line(scroll_y + y, self.size.width)
        return line

    def _render_line(self, y: int, width: int) -> Strip:
        if y >= len(self._lines):
            return Strip.blank(width, self.rich_style)

        is_selected = y == self.cursor_pos
        modifier = self._get_modifier(y)
        key = self._LineCacheKey(y + self._start_line, width, is_selected, modifier)
        if key in self._line_cache:
            return self._line_cache[key]

        style_prefix = "codepanel-"
        if is_selected:
            style_prefix += "-selected"

        modifier_style = self.get_component_styles(f"{style_prefix}-modifier")
        modifier = Segment(
            f"{modifier:{modifier_style.width}}", modifier_style.rich_style
        )

        linenum, source = self._lines[y]
        linenum = Segment(
            linenum, self.get_component_rich_style(f"{style_prefix}-linenum")
        )
        source_style = self.get_component_rich_style(f"{style_prefix}-code")
        source = Segment(source, source_style)

        strip = (
            Strip([modifier, linenum, source])
            .adjust_cell_length(width, source_style)
            .crop(0, width)
        )

        self._line_cache[key] = strip
        return strip

    def _watch_cursor_pos(self, old_pos: int, new_pos: int) -> None:
        if not self._lines:
            return

        self.refresh(self._get_region_for_row(old_pos))
        self.refresh(self._get_region_for_row(new_pos))
        if self.show_ancestors and not self._ancestor_locked:
            self._refresh_ancestors(new_pos)

        self.scroll_to_show_row(new_pos)

        if new_pos < len(self._trace.steps):
            step = self._trace.steps[new_pos]
        else:
            step = None
        self.post_message(self.ActiveLineChanged(new_pos, step))

    def _get_region_for_row(self, row: int) -> Region:
        current_width = self.size.width
        region = Region(0, row, current_width, 1)
        return region.translate(-self.scroll_offset)

    def _get_region_for_step(self, step: simulator.Step):
        return self._get_region_for_row(step.index)

    def _refresh_step(self, step: simulator.Step):
        self.refresh(self._get_region_for_step(step))

    def _watch_show_ancestors(self, old_val: bool, new_val: bool) -> None:
        del old_val
        if new_val:
            self._refresh_ancestors(self.cursor_pos)
        else:
            self._highlighted_ancestors.clear()
            self._highlighted_inputs.clear()

    def _refresh_ancestors(self, row: int):
        step = self._trace.steps[row]
        self._ancestor_chain_root_step_index = step.index
        ancestors, inputs = _collect_contributors(step)

        stale_ancestors = self._highlighted_ancestors - ancestors
        stale_inputs = self._highlighted_inputs - inputs

        self._highlighted_ancestors = ancestors
        self._highlighted_inputs = inputs

        for ancestor in stale_ancestors | self._highlighted_ancestors:
            self._refresh_step(ancestor.step)

    def _get_modifier(self, row: int) -> str:
        if not self.show_ancestors:
            return ""

        step = self._trace.steps[row]
        for ancestor in self._highlighted_ancestors:
            if ancestor.step == step:
                if step.index == self._ancestor_chain_root_step_index:
                    return "<=>" if self._ancestor_locked else "="
                return "+"
        return ""

    @property
    def visible_rows(self) -> int:
        return self.size.height - 1

    @property
    def selected_step(self) -> Optional[simulator.Step]:
        if not self._trace:
            return None
        return self._trace.steps[self.cursor_pos]

    @property
    def selected_step_is_locked_root(self) -> bool:
        step = self.selected_step
        if not step:
            return False
        return step.index == self._ancestor_chain_root_step_index

    def scroll_to_show_row(self, row: int) -> None:
        """Scrolls this view to ensure that the given row is onscreen."""
        first_visible = int(self.scroll_y)
        if row < first_visible:
            self.scroll_to(0, row)
            return

        last_visible = first_visible + self.visible_rows
        if row > last_visible:
            self.scroll_to(0, max(0, row - self.visible_rows))

    def _action_cursor_up(self):
        if self.cursor_pos > 0:
            self.cursor_pos -= 1

    def _action_cursor_down(self):
        if self.cursor_pos < len(self._lines) - 1:
            self.cursor_pos += 1

    def _action_cursor_pageup(self):
        self.cursor_pos = max(self.cursor_pos - self.visible_rows, 0)

    def _action_cursor_pagedown(self):
        self.cursor_pos = min(self.cursor_pos + self.visible_rows, len(self._lines) - 1)

    def _action_cursor_home(self):
        self.cursor_pos = 0

    def _action_cursor_end(self):
        self.cursor_pos = len(self._lines) - 1

    def _remove_highlight(self, row: Tuple[Label, Label, Label]) -> None:
        for widget in row:
            widget.remove_class("selected")

    def _add_highlight(self, row: Tuple[Label, Label, Label]) -> None:
        for widget in row:
            widget.add_class("selected")

    def _action_toggle_ancestors(self):
        # Hack for contextual actions.
        if self.show_ancestors:
            self._bindings.bind("a", "toggle_ancestors", "Show ancestors")
            del self._bindings.keys["f"]
            del self._bindings.keys["space"]
            self._ancestor_locked = False
        else:
            self._bindings.bind("a", "toggle_ancestors", "Hide ancestors")
            self._bindings.bind("f", "toggle_filtering", "Show ancestors only")
            self._bindings.bind("space", "toggle_ancestor_lock", "Lock ancestor")
        self.screen.focused = None
        self.focus()

        self.show_ancestors = not self.show_ancestors

    def _action_toggle_filtering(self):
        pass

    def _action_toggle_ancestor_lock(self):
        is_new_lock = self._ancestor_locked and self.selected_step_is_locked_root

        if not self._ancestor_locked or not is_new_lock:
            self._ancestor_locked = not self._ancestor_locked

        if not self._ancestor_locked or is_new_lock:
            self._refresh_ancestors(self.cursor_pos)
        self._refresh_step(self.selected_step)


def _collect_contributors(
    current: simulator.Step, mac_ilu_filer: Optional[str] = None
) -> Tuple[Set[simulator.Ancestor], Set[simulator.RegisterReference]]:
    """Returns a tuple of flattened Ancestor and RegisterReferences contributing to the inputs of the given Step."""
    flat_ancestors = set()
    flat_inputs = set()

    def add_recursive_ancestors(ancestors: List[simulator.Ancestor]) -> None:
        for link in ancestors:
            if link in flat_ancestors:
                continue

            flat_ancestors.add(link)

            new_ancestors, new_inputs = link.step.get_ancestors_for_stage(
                link.mac_or_ilu
            )
            add_recursive_ancestors(new_ancestors)
            flat_inputs.update(new_inputs)

    if mac_ilu_filer:
        keys = set(mac_ilu_filer)
    else:
        keys = {"mac", "ilu"}
    starting_list = [
        simulator.Ancestor(current, key) for key in keys if current.has_stage(key)
    ]
    add_recursive_ancestors(starting_list)

    return flat_ancestors, flat_inputs
