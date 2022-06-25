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
* "o" will toggle the display of the outputs of the selected line.

# Helpful hints

* You can convert the contents of a [xemu](https://github.com/mborgerson/xemu) vertex shader using [RenderDoc](https://renderdoc.org/) to examine the draw and running it through https://github.com/abaire/renderdoc_util/blob/main/util/xemu_shader_to_nv2a.py to sanitize it.
* You can set initial values with csv dumps from RenderDoc (use `-h` to see the appropriate commands, the mesh view will have the input register values and you can expand the uniforms in the pipeline view to get the constant registers)

# Example output
```
 File    Export                                                                                                                                                                                                                            
*  0 a  MUL R6, v1, c[121]                                                                                                                                                                                                                 
   1    MUL R4, v3, c[120]                                                                                                                                                                                                                 
   2    DP4 R5.x, R6, c[128] + MOV oD0.w, v0.w                                                                                                                                                                                             
   3 >  DP4 R5.y, R6, c[129]                                                                                                                                                                                                               
   4    DP4 R5.z, R6, c[130]                                                                                                                                                                                                               
   5    DP4 R5.w, R6, c[131]                                                                                                                                                                                                               
   6 =  ADD R11.xyz, R6.xyz, -c[136].xyz                                                                                                                                                                                                   
   7    ADD R10.yzw, R6.yzx, -c[137].yzx                                                                                                                                                                                                   
   8    MUL R2.xyz, R11.xyz, R11.xyz                                                                                                                                                                                                       
   9    DP3 R2.x, c[135].z, R2.xyz                                                                                                                                                                                                         
  10    MUL R2.yzw, R10.yzw, R10.yzw                                                                                                                                                                                                       
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 R1, R15, R3, c[100], c[101], c[102], c[103], c[104], c[105], c[106], c[107], c[108], c[109], c[110], c[111], c[112], c[113], c[114], c[115], c[120], c[121], c[128], c[129], c[130], c[131], c[135], c[136], c[137], c[138], c[139],      
 c[140], c[141], c[142], c[143], c[144], c[145], c[146], c[147], c[58], c[59], c[96], c[97], c[98], c[99], v0, v1, v3                                                                                                                      
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Result: R5.y: -993.2607421875, 1464.3172607421875, 0.0, 0.0     
 ```
