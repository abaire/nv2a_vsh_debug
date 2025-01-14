"""Setuptools entrypoint for debugger."""

from nv2a_debug import debugger


def run():
    """Run the debugger."""
    debugger.entrypoint()
