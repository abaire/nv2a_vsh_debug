"""Provides a widget to render and navigate nv2a vsh assembly code."""
from dataclasses import dataclass
from typing import FrozenSet
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from rich.segment import Segment
from rich.style import Style
from textual.app import Binding
from textual.geometry import Region
from textual.geometry import Size
from textual.messages import Message
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widgets import Label

from nv2adbg.simulator import Ancestor
from nv2adbg.simulator import RegisterReference
from nv2adbg.simulator import Step
from nv2adbg.simulator import Trace


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
        "codepanel--code-contributing-component",
        "codepanel--selected-modifier",
        "codepanel--selected-linenum",
        "codepanel--selected-code",
        "codepanel--selected-code-contributing-component",
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
    _CodePanel .codepanel--code-contributing-component {
        background: $background;
        color: $secondary;
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
    _CodePanel .codepanel--selected-code-contributing-component {
        background: $primary;
        color: $secondary;
    }
    """

    cursor_pos = reactive(0, always_update=True)
    show_ancestors = reactive(False)

    class ActiveLineChanged(Message):
        """Sent when the current source line changes.

        Properties:
            linenum: int - The new line number.
            step: Optional[Step] - The Step at the new line.
        """

        def __init__(self, linenum: int, step: Optional[Step]) -> None:
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
        self._trace: Optional[Trace] = None
        self._lines: List[Tuple[str, Step]] = []
        self._start_line: int = 0

        # The root of the ancestor chain (the current cursor position in normal
        # mode, but may be locked to an arbitrary instruction). This is the
        # Step::index rather than a row index.
        self._ancestor_chain_root_step_index: Optional[int] = None
        self._ancestor_locked: bool = False
        self._highlighted_ancestors: Set[Ancestor] = set()
        self._highlighted_inputs: Set[RegisterReference] = set()

    def set_shader_trace(self, trace: Trace):
        self._trace = trace

        self._lines.clear()
        self._start_line = 0
        self.cursor_pos = 0

        if not trace:
            self.virtual_size = Size(self.size.width, 0)
        else:
            linenum_width = len(str(len(self._trace.steps)))
            for step in self._trace.steps:
                linenum = step.index + 1
                self._lines.append(
                    (
                        f"{linenum: >{linenum_width}}  ",
                        step,
                    )
                )

            self.virtual_size = Size(self.size.width, len(trace.steps))
            self.post_message(
                self.ActiveLineChanged(self.cursor_pos, self._trace.steps[0])
            )

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        line = self._render_line(scroll_y + y, self.size.width)
        return line

    def _render_line(self, y: int, width: int) -> Strip:
        if y >= len(self._lines):
            return Strip.blank(width, self.rich_style)

        is_selected = y == self.cursor_pos
        modifier = self._get_modifier(y)

        style_prefix = "codepanel-"
        if is_selected:
            style_prefix += "-selected"

        modifier_style = self.get_component_styles(f"{style_prefix}-modifier")
        modifier = Segment(
            f"{modifier:{modifier_style.width}}", modifier_style.rich_style
        )

        linenum, step = self._lines[y]
        linenum = Segment(
            linenum, self.get_component_rich_style(f"{style_prefix}-linenum")
        )
        source_style_name = f"{style_prefix}-code"
        source = self._build_source_segments(step, source_style_name)

        strip = (
            Strip([modifier, linenum, *source])
            .adjust_cell_length(width, self.get_component_rich_style(source_style_name))
            .crop(0, width)
        )

        return strip

    def _build_source_segments(
        self, step: Step, source_style_name: str
    ) -> List[Segment]:
        source_style = self.get_component_rich_style(source_style_name)

        if self.show_ancestors and step.index != self._ancestor_chain_root_step_index:
            ancestors = self._get_ancestor_relationships(step)
            if ancestors:
                stage_ancestors = {"mac": [], "ilu": []}
                for ancestor in ancestors:
                    stage_ancestors[ancestor.mac_or_ilu].append(ancestor)

                contributing_style = self.get_component_rich_style(
                    source_style_name + "-contributing-component"
                )
                step_dict = step.to_dict()
                segments = [
                    _build_contributing_source_segments(
                        step_dict["instruction"][stage],
                        stage_ancestors[stage],
                        source_style,
                        contributing_style,
                    )
                    for stage in ["mac", "ilu"]
                    if step_dict["instruction"][stage]
                ]

                flattened = segments[0]
                for additional in segments[1:]:
                    flattened.append(Segment(" + ", source_style))
                    flattened.extend(additional)
                return flattened

        return [Segment(step.source, source_style)]

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

    def _get_region_for_step(self, step: Step):
        return self._get_region_for_row(step.index)

    def _refresh_step(self, step: Step):
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

    def _get_ancestor_relationships(self, step: Step) -> List[Ancestor]:
        """Returns all Ancestor relationships associated with the given Step."""
        return [a for a in self._highlighted_ancestors if a.step == step]

    def _get_modifier(self, row: int) -> str:
        if not self.show_ancestors:
            return ""

        step = self._trace.steps[row]
        if self._get_ancestor_relationships(step):
            if step.index == self._ancestor_chain_root_step_index:
                return "<=>" if self._ancestor_locked else "="
            return "+"
        return ""

    @property
    def visible_rows(self) -> int:
        return self.size.height - 1

    @property
    def selected_step(self) -> Optional[Step]:
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
    current: Step, mac_ilu_filer: Optional[str] = None
) -> Tuple[Set[Ancestor], Set[RegisterReference]]:
    """Returns a tuple of flattened Ancestor and RegisterReferences contributing to the inputs of the given Step."""
    flat_ancestors = set()
    flat_inputs = set()

    def add_recursive_ancestors(ancestors: List[Ancestor]) -> None:
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

    def extract_refs(refs: List[RegisterReference]) -> FrozenSet[Tuple[str, str]]:
        return frozenset(set([(r.raw_name, r.mask) for r in refs]))

    starting_list = [
        Ancestor(current, key, extract_refs(current.outputs[key]))
        for key in keys
        if current.has_stage(key)
    ]
    add_recursive_ancestors(starting_list)

    return flat_ancestors, flat_inputs


def _build_contributing_source_segments(
    info: dict,
    ancestors: List[Ancestor],
    source_style: Style,
    contributing_style: Style,
) -> List[Segment]:
    def source(text: str) -> Segment:
        return Segment(text, source_style)

    def contrib(text: str) -> Segment:
        return Segment(text, contributing_style)

    def has_applicable_ancestor(register: str) -> bool:
        """Checks all ancestors to see if any reference `register`."""
        for ancestor in ancestors:
            for r, _ in ancestor.components:
                if r == register:
                    return True
        return False

    def stylize_mask(register: str, component: str) -> Segment:
        """Check all ancestors for references to `register` to see if `component` is in the associated mask."""
        for ancestor in ancestors:
            for r, mask in ancestor.components:
                if r == register and component in mask:
                    return contrib(component)
        return source(component)

    def stylize_output(output: str) -> List[Segment]:
        components = output.split(".")
        register = components[0]
        ret = [contrib(register)]

        if len(components) < 2 and has_applicable_ancestor(register):
            mask = "xyzw"
        else:
            mask = components[1]

        if mask:
            ret.append(source("."))
            ret.extend([stylize_mask(register, c) for c in mask])

        return ret

    input_str = ", ".join(info["inputs"])

    ret = []
    for output in info["outputs"]:
        op = [source(info["mnemonic"])]
        op.append(source(" "))

        if ancestors:
            op.extend(stylize_output(output))
        else:
            op.append(source(output))

        op.append(source(", "))
        op.append(source(input_str))

        ret.append(op)

    flattened = ret[0]
    for additional in ret[1:]:
        flattened.append(source(" + "))
        flattened.extend(additional)
    return flattened
