"""Setuptools entrypoint for debugger."""
from . import debugger


def run():
    """Run the debugger."""
    debugger.entrypoint()
