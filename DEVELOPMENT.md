# Development with Intellij/PyCharm

To run the app w/ the textual dev tools, create a run configuration using:

* Module name: `textual.cli`
* Parameters: `run --dev nv2adbg/debugger.py -- <debugger_params>`

and set the working path to this top-level directory.

You can then launch `textual console` in another console window to capture log
output (see [the docs](https://textual.textualize.io/guide/devtools/).
