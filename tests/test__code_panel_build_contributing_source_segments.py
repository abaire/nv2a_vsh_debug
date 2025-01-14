from __future__ import annotations

from rich.segment import Segment
from rich.style import Style

from nv2a_debug._code_panel import _build_contributing_source_segments
from nv2a_debug.py_nv2a_vsh_emu import Nv2aVshStep
from nv2a_debug.simulator import Ancestor, Context, Step

_SOURCE_STYLE = Style(color="red")
_CONTRIB_STYLE = Style(color="blue")


class TestBuildContributingSourceSegments:
    """Tests for _build_contributing_source_segments."""

    def test_no_ancestors_returns_only_source_style(self):
        """Any invocation with no ancestors must render everything with source_style."""
        info = info_dict("MOV", ["oD0"], ["-v1"])
        ancestors = []

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("oD0", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_single_ancestor_and_matching_output_mask(self):
        """Given Ancestor( [(R0, xy)] ) and output R0.xy the output should be fully contrib styled."""
        info = info_dict("MOV", ["R0.xy"], ["-v1"])
        ancestors = [ancestor([("R0", "xy")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _CONTRIB_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_single_ancestor_and_subset_matching_output_mask(self):
        """Given Ancestor( [(R0, xy)] ) and output R0.y the output should be fully contrib styled."""
        info = info_dict("MOV", ["R0.y"], ["-v1"])
        ancestors = [ancestor([("R0", "xy")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_single_ancestor_and_superset_matching_output_mask(self):
        """Given Ancestor( [(R0, xy)] ) and output R0.yzx the non-matching masks should remain source styled."""
        info = info_dict("MOV", ["R0.yzx"], ["-v1"])
        ancestors = [ancestor([("R0", "xy")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment("z", _SOURCE_STYLE),
            Segment("x", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_single_ancestor_and_overlapping_input(self):
        """Given Ancestor( [(R0, xy)] ), output R0.xy, input R0.yx the input should never be contrib styled."""
        info = info_dict("MOV", ["R0.xy"], ["R0.yx"])
        ancestors = [ancestor([("R0", "xy")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _CONTRIB_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("R0.yx", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_single_ancestor_disjoint_mask_is_ignored(self):
        """Given Ancestor( [(R0, z)] ), output R0.xy, input R0.yx the input should never be contrib styled."""
        info = info_dict("MOV", ["R0.xy"], ["-v1"])
        ancestors = [ancestor([("R0", "z")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _SOURCE_STYLE),
            Segment("y", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_single_ancestor_disjoint_register_is_ignored(self):
        """Given Ancestor( [(R1, x), (R0, y] ), output R0.xy, only the matching register mask should be applied"""
        info = info_dict("MOV", ["R0.xy"], ["-v1"])
        ancestors = [ancestor([("R1", "x"), ("R0", "y")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _SOURCE_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_disjoint_register_is_ignored(self):
        """Given Ancestor( [(R1, x), (R0, y] ), output R0.xy, only the matching register mask should be applied"""
        info = info_dict("MOV", ["R0.xy"], ["-v1"])
        ancestors = [ancestor([("R1", "x")]), ancestor([("R0", "y")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _SOURCE_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_overlapping_ancestors_are_merged(self):
        """Given Ancestor([(R0, x]), Ancestor([(R0, y]), output R0.xy: both masks are applied."""
        info = info_dict("MOV", ["R0.xy"], ["-v1"])
        ancestors = [ancestor([("R0", "x")]), ancestor([("R0", "y")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _CONTRIB_STYLE),
            Segment("y", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected

    def test_implicit_full_mask_is_expanded(self):
        """Given Ancestor([(R0, w]), output R0: the output is expanded to R0.xyz<w>."""
        info = info_dict("MOV", ["R0"], ["-v1"])
        ancestors = [ancestor([("R0", "w")])]

        result = _build_contributing_source_segments(info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE)

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _CONTRIB_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("x", _SOURCE_STYLE),
            Segment("y", _SOURCE_STYLE),
            Segment("z", _SOURCE_STYLE),
            Segment("w", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-v1", _SOURCE_STYLE),
        ]
        assert result == expected


def info_dict(mnemonic: str, outputs: list[str], inputs: list[str]) -> dict:
    """Generates a Step.to_dict with the given values"""
    return {
        "mnemonic": mnemonic,
        "outputs": outputs,
        "inputs": inputs,
    }


def ancestor(components: list[tuple[str, str]]) -> Ancestor:
    mock_step = Step(0, source="TEST", state=Context(), instruction=Nv2aVshStep([]))
    return Ancestor(step=mock_step, mac_or_ilu="TEST", components=frozenset(components))
