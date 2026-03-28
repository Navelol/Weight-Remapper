<img width="1216" height="315" alt="Logo" src="https://github.com/user-attachments/assets/00a13e01-0b6c-4de6-8092-a793eaf79d7e" />

A Blender addon that intelligently remaps vertex groups on a mesh to match the bone names of a different armature. Built for the VRChat avatar community but works with any humanoid rig.

![Blender](https://img.shields.io/badge/Blender-4.5%2B-orange?logo=blender&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

---

## What it does

When you take a clothing mesh or accessory rigged for one avatar base and want to use it on a different base with different bone naming conventions, every vertex group needs to be renamed to match. Doing this by hand for 50+ bones is tedious and error-prone.

Weight Remapper analyses both the source mesh's vertex groups and the target armature's bone names, figures out what matches what using a semantic dictionary of known body part keywords, and presents you with a clean before/after mapping table to review and apply in one click.

It understands:
- All major VRChat naming conventions (L/R prefix, Left/Right prefix, dot suffix, underscore suffix)
- Twist and rotation helper bones (ZArm, Twist_Wrist, Elbow_Twist, etc.)
- Secondary physics bones (breast, glute, hip dip, tummy, jiggle, volume bones)
- Hair bone chains (auto-detected and skipped)
- Clothing/accessory bones (auto-detected and skipped)
- Adult anatomy bones (surfaced for manual review, never silently dropped)
- Finger chains across all common indexing styles
- Individual toe bones

![blender_9FOhwF8EGN](https://github.com/user-attachments/assets/b425b0b2-c142-4d7d-8726-f4726a092093)

---

## Installation

1. Download the latest `bone_remapper.zip` from the [Releases](../../releases) page
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the downloaded zip
4. Enable **Weight Remapper** in the list

Requires **Blender 4.5 or later** *(might work with earlier versions but haven't tested)*.

---

## Usage

1. Open the **N-panel** in the 3D Viewport (press `N`)
2. Go to the **Rigging** tab → **Weight Remapper**
3. Set **Mesh** to the clothing or accessory mesh you want to retarget
4. Set **Armature** to the target avatar armature
5. Click **Analyse**
6. Review the results — four buckets:
   - √ **Matched** — confident auto-match, good to go
   - ⚠ **Needs Review** — matched but low confidence, or needs manual confirmation
   - ? **Unmatched** — source group with no target found
   - ◎ **Missing Source** — target bone in the right region but no source group covers it
7. Fix anything in yellow. For missing rows, click the left picker to assign a source vertex group.
8. Click **Apply Remap**

### Merging weights

If you pick a target bone that's already mapped by another source group, the row automatically switches to **merge mode** (shown with a ⊕ arrow and an automerge toggle). On apply, instead of renaming, the weights are added together and clamped to 1.0 — useful for collapsing HipDips into Hips, or combining physics bone weights.

### Presets

Save your mapping as a JSON file with the **Save** button and reload it later with **Load**. Useful for reusing a known mapping between two specific base meshes.

### Debug log

Every time you run Analyse, a `bone_remapper_debug.txt` file is written next to the addon files. It contains the full normalizer and classifier output for every bone on both sides — useful for diagnosing unexpected matches.

---

## How it works

Each bone name goes through a normalizer pipeline:

1. Strip namespaces (`mixamorig:`, `DEF-`, `ORG-`)
2. Extract side token (`L`/`R`/`Left`/`Right` — prefix, suffix, or anywhere in the name)
3. Extract numeric index (`.001`, `_0`, `02`, etc.)
4. Strip Z-prefix helpers (`ZArm` → `Arm`, flagged as helper type)
5. Tokenize on delimiters and camelCase boundaries
6. Look up against a semantic dictionary of ~35 body part categories

The matcher then pairs source and target bones using a four-level fallback:
1. Exact name match (instant)
2. Category + side match with topology tiebreaker (uses the target armature's hierarchy to prefer bones that have the expected children — e.g. prefers the forearm bone that actually connects to a wrist over a leaf elbow helper)
3. Category only match (side mismatch — flagged as review)
4. No match found

After matching, a sibling consistency pass checks twist bones against their same-side body bone mappings and flags any region disagreements.

---

## Supported naming conventions

| Convention | Example | Notes |
|---|---|---|
| A — L/R prefix | `L Arm`, `R ZForeArm Twist` | Z-prefix = helper/twist |
| B — Left/Right prefix | `Left arm`, `LittleFinger1_L` | Body lowercase, fingers suffix |
| B2 — snake_case fingers | `Index_Finger_0_L` | 0-based indexing |
| C — dot suffix | `Shoulder.L`, `Arm.L` | Blender native mirror convention |
| D — underscore suffix | `Arm_L`, `Leg_L` | Consistent on all bones |

Mixed conventions within the same rig are handled — each bone is matched independently.

---

## Known limitations

- **No source hierarchy** — clothing meshes have vertex groups but no armature hierarchy. When a rigger names their forearm bone "Elbow", the twist bone (`Elbow_Twist`) will be classified by name alone and may land in the wrong twist slot. The topology tiebreaker only works on the **target** armature side. The debug log will show medium confidence on these rows.
- **Face bones** — not in scope for v0.1. Most VRChat avatars use blendshapes for facial animation anyway.
- **IK targets / pole bones** — skipped. These don't carry vertex weights.
- **Spine count mismatch** — if source has 1 spine bone and target has 3, best-effort index matching is used. Flag as review.

---

## Contributing

PRs welcome. If you have a rig with a naming convention that's not handled well, open an issue and paste the output of the debug log — that's all the information needed to add support for it.

### Submitting your rig's hierarchy

The more naming conventions in the dictionary, the better the auto-matching gets for everyone. If your rig isn't matching well, you can submit its bone hierarchy by running the included script in Blender:

1. Select your armature in the viewport
2. Go to the **Scripting** tab
3. Click **New**, paste in the contents of this script into the text editor:
```python
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
```

4. Hit **Run Script**
5. Open the **Text Editor**, click the dropdown at the top, select **full_hierarchy**
6. Copy the contents and paste it into a [new GitHub issue](../../issues/new) with the title `Rig hierarchy: [base name]`

That's it. No Blender knowledge required beyond that, and no personal info is included — it's just bone names.

![eA3NrbjQ8l](https://github.com/user-attachments/assets/f4131e82-3f48-409e-8256-a546768a2b30)

---

## License

MIT — do whatever you want with it.
