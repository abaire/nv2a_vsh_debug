"""Provides a widget to render and navigate nv2a vsh assembly code."""

# ruff: noqa: RUF012 Mutable class attributes should be annotated with `typing.ClassVar`

# Textual event method handlers must take positional arguments.
# ruff: noqa: FBT001 Boolean-typed positional argument in function definition

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.segment import Segment
from textual.app import Binding
from textual.geometry import Region, Size
from textual.messages import Message
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

if TYPE_CHECKING:
    from rich.style import Style
    from textual.widgets import Label

from nv2a_debug.simulator import Ancestor, RegisterReference, Step, Trace, canonicalize_register_name


class TraceView:
    """Provides a filtered view of a Trace by following the ancestry of a Step."""

    def __init__(self, trace: Trace, root_step: Step | None = None):
        self._trace: Trace = trace
        self._ancestors: set[Ancestor] | None = None
        self._inputs: set[RegisterReference] | None = None
        self.filtered_steps: list[Step] = self._trace.steps
        self._root_step: Step | None = root_step

        self.set_ancestor_root(root_step)

    def set_ancestor_root(self, root_step: Step | None):
        """Sets the root of the filtered view."""
        self._root_step = root_step
        if not root_step:
            self._ancestors = None
            self._inputs = None
            self.filtered_steps = self._trace.steps
            return

        ancestors, inputs = _collect_contributors(root_step)
        self._ancestors = ancestors
        self._inputs = inputs

        included_steps = {a.step for a in ancestors}
        self.filtered_steps = [s for s in self._trace.steps if s in included_steps]

    def get_step(self, step_index: int) -> tuple[int, Step]:
        """Returns the filtered index and step with the given program index."""
        for idx, s in enumerate(self.filtered_steps):
            if s.index == step_index:
                return idx, s

        msg = f"Step index '{step_index}' not present in filtered view"
        raise IndexError(msg)

    def get_step_at_display_index(self, index: int) -> Step:
        """Returns the Step at the given offset within the filtered view."""
        return self.filtered_steps[index]

    @property
    def is_filtered(self) -> bool:
        return self._root_step is not None


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
        "codepanel--code-input-component",
        "codepanel--selected-modifier",
        "codepanel--selected-linenum",
        "codepanel--selected-code",
        "codepanel--selected-code-contributing-component",
        "codepanel--selected-code-input-component",
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
    _CodePanel .codepanel--code-input-component {
        background: $background;
        color: $success;
        text-style: underline;
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
        color: $secondary-lighten-1;
    }
    _CodePanel .codepanel--selected-code-input-component {
        background: $primary;
        color: $success-lighten-2;
        text-style: underline;
    }
    """

    _FILTER_ENABLE_HELP_TEXT = "Show ancestors only"
    _FILTER_DISABLE_HELP_TEXT = "Show all instructions"

    cursor_pos = reactive(0, always_update=True)
    show_ancestors = reactive(False)

    class ActiveLineChanged(Message):
        """Sent when the current source line changes.

        Properties:
            linenum: int - The new line number.
            step: Step | None - The Step at the new line.
        """

        def __init__(self, linenum: int, step: Step | None) -> None:
            """linenum - The new line number."""
            super().__init__()
            self.linenum = linenum
            self.step = step

    def __init__(self) -> None:
        super().__init__()
        self._trace: Trace | None = None
        self._trace_view: TraceView | None = None
        self._lines: list[tuple[str, Step]] = []
        self._start_line: int = 0

        # The root of the ancestor chain (the current cursor position in normal
        # mode, but may be locked to an arbitrary instruction). This is the
        # Step::index rather than a row index.
        self._ancestor_chain_root_step_index: int | None = None
        self._ancestor_locked: bool = False
        self._highlighted_ancestors: set[Ancestor] = set()
        self._highlighted_inputs: set[RegisterReference] = set()

    def set_shader_trace(self, trace: Trace):
        self._trace = trace
        self._trace_view = TraceView(trace)

        self._lines.clear()
        self._start_line = 0
        self.cursor_pos = 0

        if not trace:
            self.virtual_size = Size(self.size.width - 1, 0)
        else:
            self._rebuild_lines()

    def _rebuild_lines(self):
        self._lines.clear()
        linenum_width = len(str(len(self._trace.steps)))
        for step in self._trace_view.filtered_steps:
            linenum = step.index + 1
            self._lines.append(
                (
                    f"{linenum: >{linenum_width}}  ",
                    step,
                )
            )

        # TODO: properly measure max size. Some ancestor tracing interactions can grow the step length by adding masks.
        # Maximum visible length is the widget boundaries - 2 to account for the scroll bar.
        max_line_length = self.size.width - 2
        self.virtual_size = Size(max_line_length, len(self._trace_view.filtered_steps))
        self.post_message(self.ActiveLineChanged(self.cursor_pos, self._trace_view.filtered_steps[0]))

    def render_line(self, y: int) -> Strip:
        _scroll_x, scroll_y = self.scroll_offset
        return self._render_line(scroll_y + y, self.size.width)

    def _render_line(self, y: int, width: int) -> Strip:
        if y >= len(self._lines):
            return Strip.blank(width, self.rich_style)

        is_selected = y == self.cursor_pos
        modifier_character = self._get_modifier(y)

        style_prefix = "codepanel-"
        if is_selected:
            style_prefix += "-selected"

        modifier_style = self.get_component_styles(f"{style_prefix}-modifier")
        modifier = Segment(f"{modifier_character:{modifier_style.width}}", modifier_style.rich_style)

        linenum_str, step = self._lines[y]
        linenum = Segment(linenum_str, self.get_component_rich_style(f"{style_prefix}-linenum"))
        source_style_name = f"{style_prefix}-code"
        source = self._build_source_segments(step, source_style_name)

        return (
            Strip([modifier, linenum, *source])
            .adjust_cell_length(width, self.get_component_rich_style(source_style_name))
            .crop(0, width)
        )

    def _build_source_segments(self, step: Step, source_style_name: str) -> list[Segment]:
        source_style = self.get_component_rich_style(source_style_name)

        if self.show_ancestors:
            if step.index == self._ancestor_chain_root_step_index:
                contributed_style = self.get_component_rich_style(source_style_name + "-contributing-component")
                input_style = self.get_component_rich_style(source_style_name + "-input-component")
                return self._build_highlighted_input_source_segments(step, source_style, contributed_style, input_style)

            ancestors = self._get_ancestor_relationships(step)
            if ancestors:
                stage_ancestors: dict[str, list[Ancestor]] = {"mac": [], "ilu": []}
                for ancestor in ancestors:
                    stage_ancestors[ancestor.mac_or_ilu].append(ancestor)

                contributing_style = self.get_component_rich_style(source_style_name + "-contributing-component")
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
                return _flatten_composite_step_segments(segments, source_style)

        return [Segment(step.source, source_style)]

    def _build_highlighted_input_source_segments(
        self,
        step: Step,
        source_style: Style,
        contributed_style: Style,
        input_style: Style,
    ) -> list[Segment]:
        info = step.to_dict()
        return _build_ancestor_root_segments(
            info["instruction"],
            self._highlighted_ancestors,
            source_style,
            contributed_style,
            input_style,
        )

    def _watch_cursor_pos(self, old_pos: int, new_pos: int) -> None:
        if not self._lines:
            return

        self.refresh(self._get_region_for_row(old_pos))
        self.refresh(self._get_region_for_row(new_pos))
        if self.show_ancestors and not self._ancestor_locked:
            self._refresh_ancestors(new_pos)

        self.scroll_to_show_row(new_pos)

        step = (
            self._trace_view.filtered_steps[new_pos]
            if self._trace_view and new_pos < len(self._trace_view.filtered_steps)
            else None
        )

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
        if not self._trace_view:
            msg = "_refresh_ancestors called without self._trace_view"
            raise ValueError(msg)

        step = self._trace_view.filtered_steps[row]
        self._ancestor_chain_root_step_index = step.index
        ancestors, inputs = _collect_contributors(step)

        stale_ancestors = self._highlighted_ancestors - ancestors

        self._highlighted_ancestors = ancestors
        self._highlighted_inputs = inputs

        for ancestor in stale_ancestors | self._highlighted_ancestors:
            self._refresh_step(ancestor.step)

    def _get_ancestor_relationships(self, step: Step) -> list[Ancestor]:
        """Returns all Ancestor relationships associated with the given Step."""
        return [a for a in self._highlighted_ancestors if a.step == step]

    def _get_modifier(self, row: int) -> str:
        if not self.show_ancestors:
            return ""

        if not self._trace_view:
            msg = "_get_modifier called without self._trace_view"
            raise ValueError(msg)

        step = self._trace_view.get_step_at_display_index(row)
        if self._get_ancestor_relationships(step):
            if step.index == self._ancestor_chain_root_step_index:
                return "<=>" if self._ancestor_locked else "="
            return "+"
        return ""

    @property
    def visible_rows(self) -> int:
        obscured_rows = 1 if self.show_horizontal_scrollbar else 0
        return self.size.height - (1 + obscured_rows)

    @property
    def selected_step(self) -> Step | None:
        if not self._trace:
            return None

        if not self._trace_view:
            msg = "selected_step called without self._trace_view"
            raise ValueError(msg)

        return self._trace_view.filtered_steps[self.cursor_pos]

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

    def _remove_highlight(self, row: tuple[Label, Label, Label]) -> None:
        for widget in row:
            widget.remove_class("selected")

    def _add_highlight(self, row: tuple[Label, Label, Label]) -> None:
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
            self._bindings.bind("f", "toggle_filtering", self._FILTER_ENABLE_HELP_TEXT)
            self._bindings.bind("space", "toggle_ancestor_lock", "Lock ancestor")
        self._refresh_bindings()

        self.show_ancestors = not self.show_ancestors

    def _action_toggle_filtering(self):
        root_step = self.selected_step

        if self._trace_view.is_filtered:
            self._bindings.bind("f", "toggle_filtering", self._FILTER_ENABLE_HELP_TEXT)
            self._trace_view.set_ancestor_root(None)
        else:
            self._bindings.bind("f", "toggle_filtering", self._FILTER_DISABLE_HELP_TEXT)
            self._trace_view.set_ancestor_root(root_step)

        self._rebuild_lines()
        self.cursor_pos = self._trace_view.get_step(root_step.index)[0]

        self._refresh_bindings()
        self.refresh()

    def _refresh_bindings(self):
        self.screen.focused = None
        self.focus()

    def _action_toggle_ancestor_lock(self):
        is_new_lock = self._ancestor_locked and self.selected_step_is_locked_root

        if not self._ancestor_locked or not is_new_lock:
            self._ancestor_locked = not self._ancestor_locked

        if not self._ancestor_locked or is_new_lock:
            self._refresh_ancestors(self.cursor_pos)
        self._refresh_step(self.selected_step)


def _collect_contributors(
    current: Step, mac_ilu_filer: str | None = None
) -> tuple[set[Ancestor], set[RegisterReference]]:
    """Returns a tuple of flattened Ancestor and RegisterReferences contributing to the inputs of the given Step."""
    flat_ancestors = set()
    flat_inputs = set()

    def add_recursive_ancestors(ancestors: list[Ancestor]) -> None:
        for link in ancestors:
            if link in flat_ancestors:
                continue

            flat_ancestors.add(link)

            new_ancestors, new_inputs = link.step.get_ancestors_for_stage(link.mac_or_ilu)
            add_recursive_ancestors(new_ancestors)
            flat_inputs.update(new_inputs)

    keys = set(mac_ilu_filer) if mac_ilu_filer else {"mac", "ilu"}

    def extract_refs(refs: list[RegisterReference]) -> frozenset[tuple[str, str]]:
        return frozenset({(r.raw_name, r.mask) for r in refs})

    starting_list = [
        Ancestor(current, key, extract_refs(current.outputs[key])) for key in keys if current.has_stage(key)
    ]
    add_recursive_ancestors(starting_list)

    return flat_ancestors, flat_inputs


def _build_contributing_source_segments(
    info: dict,
    ancestors: list[Ancestor],
    source_style: Style,
    contributing_style: Style,
) -> list[Segment]:
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

    def stylize_output(output: str) -> list[Segment]:
        components = output.split(".")
        register = components[0]
        ret = [contrib(register)]

        mask = "xyzw" if len(components) < 2 and has_applicable_ancestor(register) else components[1]  # noqa: PLR2004 Magic value used in comparison

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

    return _flatten_composite_step_segments(ret, source_style)


def _build_ancestor_root_segments(
    instruction: dict,
    ancestors: set[Ancestor],
    source_style: Style,
    contributed_style: Style,
    input_style: Style,
) -> list[Segment]:
    def source(text: str) -> Segment:
        return Segment(text, source_style)

    def contrib(text: str) -> Segment:
        return Segment(text, contributed_style)

    def unsatisfied_input(text: str) -> Segment:
        return Segment(text, input_style)

    def contributed_components(register_name: str) -> set[str]:
        """Returns a set of mask elements contributed by ancestors."""
        ret = set()
        for ancestor in ancestors:
            for register, mask in ancestor.components:
                if register == register_name:
                    ret |= set(mask)
        return ret

    def build_inputs(inputs: list[str]) -> list[Segment]:
        ret = []
        for idx, input_register in enumerate(inputs):
            if idx:
                ret.append(source(", "))

            if input_register[0] == "-":
                ret.append(source("-"))
                input_register = input_register[1:]  # noqa:  PLW2901 `for` loop variable overwritten
            reg_and_mask = input_register.split(".")
            raw_register_name = reg_and_mask[0]
            register_name = canonicalize_register_name(raw_register_name)
            contributed_mask = contributed_components(register_name)

            if len(contributed_mask) == 4:  # noqa: PLR2004 Magic value used in comparison
                # All components were contributed, so the entire reg is contributed.
                ret.append(contrib(input_register))
            elif not contributed_mask:
                # No components were contributed, so the entire reg is an input.
                ret.append(unsatisfied_input(input_register))
            else:
                mask = "xyzw" if len(reg_and_mask) == 1 else reg_and_mask[1]

                has_unsatisfied = False
                component_segments = []
                for component in mask:
                    if component in contributed_mask:
                        component_segments.append(contrib(component))
                    else:
                        component_segments.append(unsatisfied_input(component))
                        has_unsatisfied = True

                if has_unsatisfied:
                    ret.append(unsatisfied_input(raw_register_name))
                else:
                    ret.append(contrib(raw_register_name))
                ret.append(source("."))
                ret.extend(component_segments)

        return ret

    def _build_ancestor_root_stage(mac_or_ilu: str) -> list[list[Segment]]:
        info = instruction.get(mac_or_ilu)
        if not info:
            return []

        ret = []
        for output in info["outputs"]:
            op = [source(info["mnemonic"])]
            op.append(source(" "))
            op.append(source(output))
            op.append(source(", "))

            op.extend(build_inputs(info["inputs"]))
            ret.append(op)

        return ret

    segments = _build_ancestor_root_stage("mac")
    segments.extend(_build_ancestor_root_stage("ilu"))
    return _flatten_composite_step_segments(segments, source_style)


def _flatten_composite_step_segments(segments: list[list[Segment]], join_style: Style) -> list[Segment]:
    flattened = segments[0]
    for additional in segments[1:]:
        flattened.append(Segment(" + ", join_style))
        flattened.extend(additional)
    return flattened
