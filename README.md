Simulator/debugger for the original Xbox nv2a vertex shader.

# Use
Very raw instruction summary as of Jun 12, 2022:

*NOTE*: You'll need to load the file via the commandline right now, import is not implemented

## Sections

The UI is divided into two sections, the top menu and the source window. You can use the `F1` and `F2` keys to switch between sections (`1` and `2` also work to allow navigation when running under CLion for development purposes). The asterisk (`*`) in the side bar on the left indicates the active section.

### Menu window
* "e" will export the current source view to a file in the current working directory.

### Source window
* Cursor up/down in the source window navigates lines, page-up/down jump farther.
* "a" will toggle ancestry tracing for the currently selected line, marking every line that contributes to the line's outputs. 

   At the time of this writing there is no way to choose between the MAC and ILU component of a paired command, both will be traced. If you only care about one or the other, the best option is to go to the first ancestor that contributes solely to the one you care about and do the trace from there.

* Pressing "f" with ancestor tracking enabled will filter out all of the lines that do not contribute to the instruction being traced. Press "f" again to return to full source view.


# Helpful hints

* You can convert the contents of a [xemu](https://github.com/mborgerson/xemu) vertex shader using [RenderDoc](https://renderdoc.org/) to examine the draw and running it through https://github.com/abaire/renderdoc_util/blob/main/util/xemu_shader_to_nv2a.py to sanitize it.
* You can set initial values with csv dumps from RenderDoc (use `-h` to see the appropriate commands, the mesh view will have the input register values and you can expand the uniforms in the pipeline view to get the constant registers)
