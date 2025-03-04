# Tests for RegisterReference
from nv2a_debug.simulator import RegisterReference


def test_lossy_merge__identical_register_different_swizzles():
    first = RegisterReference(
        canonical_name="R3", extended_mask="xyzw", mask="xyzw", negate=False, raw_name="R3", sorted_mask="xyzw"
    )
    second = RegisterReference(
        canonical_name="R3", extended_mask="yyyy", mask="y", negate=False, raw_name="R3", sorted_mask="y"
    )

    merged = first.lossy_merge(second)

    assert merged.mask == "xyzw"
    assert merged.sorted_mask == "xyzw"


def test_lossy_merge__dissimilar_returns_self():
    first = RegisterReference(
        canonical_name="R0", extended_mask="xyzw", mask="xyzw", negate=False, raw_name="R3", sorted_mask="xyzw"
    )
    second = RegisterReference(
        canonical_name="R3", extended_mask="yyyy", mask="y", negate=False, raw_name="R3", sorted_mask="y"
    )

    merged = first.lossy_merge(second)

    assert merged == first
