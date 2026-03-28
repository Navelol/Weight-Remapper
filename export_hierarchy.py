"""
export_hierarchy.py
-------------------
Paste this into Blender's Text Editor (Scripting tab) and run it
with your armature selected. It writes the full bone hierarchy to
a text block called "full_hierarchy" which you can copy from the
Text Editor dropdown.

Useful for submitting your rig's naming convention so it can be
added to the Weight Remapper dictionary.
"""

import bpy

arm = bpy.context.active_object

if arm is None or arm.type != 'ARMATURE':
    raise Exception("Select an armature first!")

text = bpy.data.texts.new("full_hierarchy")

def print_bone(bone, depth=0):
    indent = "  " * depth
    text.write(f"{indent}{bone.name}\n")
    for child in bone.children:
        print_bone(child, depth + 1)

roots = [b for b in arm.data.bones if b.parent is None]
for root in roots:
    print_bone(root)

print(f"Done! {len(arm.data.bones)} bones written to 'full_hierarchy'")
