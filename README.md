Simulator/debugger for the original Xbox nv2a vertex shader.

# Use

Run with `--help` to see command line options.

## Menus

### File menu

Allows inputs to be configured.

## Source window

The source window is split into three areas:

1. The program view on the left shows the shader instructions
1. The inputs panel on the right shows the value of register inputs for the
   currently selected line. Components of the register that are used will be
   highlighted.
1. The outputs panel at the bottom shows the computed values of the outputs.
   Components that are written to will be highlighted.

* Cursor up/down, page-up/down, and home/end in the source window navigate
  source lines.
* "a" will toggle ancestry tracing for the currently selected line, marking
  every line that contributes to the line's outputs.
    * In tracing mode
        * "space" will allow the current line to be locked so
          moving the cursor will not change the root of the ancestor trace.
        * "f" will filter out any lines that do not contribute to the
          instruction being traced. Press "f" again to return to full source
          view.
    * _NOTE_: At the time of this writing there is no way to choose between the
      MAC and ILU component of a paired command, both will be traced. If you
      only care about one or the other, the best option is to go to the first
      ancestor that contributes solely to the one you care about and do the
      trace from there.

# Helpful hints

* You can convert the contents of a [xemu](https://github.com/mborgerson/xemu)
  vertex shader using [RenderDoc](https://renderdoc.org/) to examine the draw
  and running it
  through https://github.com/abaire/renderdoc_util/blob/main/util/xemu_shader_to_nv2a.py
  to sanitize it.
* You can set initial values with csv dumps from RenderDoc (use `-h` to see the
  appropriate commands, the mesh view will have the input register values and
  you can expand the uniforms in the pipeline view to get the constant
  registers)
