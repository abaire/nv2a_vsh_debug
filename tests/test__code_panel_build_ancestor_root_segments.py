from typing import Dict
from typing import List
from typing import Tuple
import unittest

from rich.segment import Segment
from rich.style import Style

from nv2adbg._code_panel import _build_ancestor_root_segments
from nv2adbg.simulator import Ancestor

_SOURCE_STYLE = Style(color="red")
_CONTRIB_STYLE = Style(color="blue")
_INPUT_STYLE = Style(color="green")


class TestBuildAncestorRootSegments(unittest.TestCase):
    def test_single_output_all_inputs_with_negation(self):
        """An instruction with no ancestors should tag all inputs with input style."""
        info = {"mac": info_dict("DP4", ["R0"], ["-v1", "c[98]"])}
        ancestors = []

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R0", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _INPUT_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_multiple_outputs_all_inputs_with_negation(self):
        """A multi-output instruction with no ancestors should tag all inputs with input style."""
        info = {"mac": info_dict("DP4", ["R1", "oPos"], ["-v1", "c[98]"])}
        ancestors = []

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _INPUT_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
            Segment(" + ", _SOURCE_STYLE),
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("oPos", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _INPUT_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_multiple_outputs_all_contributed_with_negation(self):
        """A multi-output instruction with all inputs covered by ancestors should tag them with contrib style."""
        info = {"mac": info_dict("DP4", ["R1", "oPos"], ["-v1", "c[98]"])}
        ancestors = [ancestor([("v1", "xyzw"), ("c98", "xyzw")])]

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _CONTRIB_STYLE),
            Segment(" + ", _SOURCE_STYLE),
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("oPos", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _CONTRIB_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_multiple_outputs_mixed_contrib_and_input(self):
        """A multi-output instruction with all inputs covered by ancestors should tag them with contrib style."""
        info = {"mac": info_dict("DP4", ["R1", "oPos"], ["-v1", "c[98]"])}
        ancestors = [ancestor([("v1", "xyzw")])]

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
            Segment(" + ", _SOURCE_STYLE),
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("oPos", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_dual_stage_multiple_outputs_mixed_contrib_and_input(self):
        info = {
            "mac": info_dict("DP4", ["R1", "oPos"], ["-v1", "c[98]"]),
            "ilu": info_dict("RSQ", ["R1.x"], ["c[98]"]),
        }
        ancestors = [ancestor([("v1", "xyzw")])]

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
            Segment(" + ", _SOURCE_STYLE),
            Segment("DP4", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("oPos", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _CONTRIB_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
            Segment(" + ", _SOURCE_STYLE),
            Segment("RSQ", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1.x", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("c[98]", _INPUT_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_mixed_component(self):
        info = {"mac": info_dict("MOV", ["R1.yzx"], ["-v1.wyx"])}
        ancestors = [ancestor([("v1", "xw")])]

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1.yzx", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _INPUT_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("w", _CONTRIB_STYLE),
            Segment("y", _INPUT_STYLE),
            Segment("x", _CONTRIB_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_multiple_ancestors_are_applied(self):
        info = {"mac": info_dict("MOV", ["R1.yzx"], ["-v1.wyx"])}
        ancestors = [ancestor([("v1", "x")]), ancestor([("v1", "w")])]

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1.yzx", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _INPUT_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("w", _CONTRIB_STYLE),
            Segment("y", _INPUT_STYLE),
            Segment("x", _CONTRIB_STYLE),
        ]
        self.assertEqual(result, expected)

    def test_multiple_masks_in_one_ancestor_are_applied(self):
        info = {"mac": info_dict("MOV", ["R1.yzx"], ["-v1.wyx"])}
        ancestors = [ancestor([("v1", "x"), ("v1", "zw")])]

        result = _build_ancestor_root_segments(
            info, ancestors, _SOURCE_STYLE, _CONTRIB_STYLE, _INPUT_STYLE
        )

        expected = [
            Segment("MOV", _SOURCE_STYLE),
            Segment(" ", _SOURCE_STYLE),
            Segment("R1.yzx", _SOURCE_STYLE),
            Segment(", ", _SOURCE_STYLE),
            Segment("-", _SOURCE_STYLE),
            Segment("v1", _INPUT_STYLE),
            Segment(".", _SOURCE_STYLE),
            Segment("w", _CONTRIB_STYLE),
            Segment("y", _INPUT_STYLE),
            Segment("x", _CONTRIB_STYLE),
        ]
        self.assertEqual(result, expected)


def info_dict(mnemonic: str, outputs: List[str], inputs: List[str]) -> Dict:
    """Generates a Step.to_dict with the given values"""
    return {
        "mnemonic": mnemonic,
        "outputs": outputs,
        "inputs": inputs,
    }


def ancestor(components: List[Tuple[str, str]]) -> Ancestor:
    return Ancestor(step="TEST", mac_or_ilu="TEST", components=frozenset(components))


if __name__ == "__main__":
    unittest.main()
