bl_info = {
    "name":        "Weight Remapper",
    "author":      "Evan Pierce",
    "version":     (0, 1, 0),
    "blender":     (4, 5, 0),
    "location":    "N-Panel > Rigging > Weight Remapper",
    "description": "Remap vertex groups on a mesh to match a new armature's bone names",
    "category":    "Rigging",
}

import bpy
import sys
import os
import importlib

_addon_dir = os.path.dirname(__file__)
if _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)

import remapper
importlib.reload(remapper)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _short_note(bucket, confidence, notes):
    """Return a compact, human-readable status line."""
    if bucket == "matched" and confidence == "exact":
        return ""
    if bucket == "matched" and confidence == "high":
        return ""
    if bucket == "matched" and confidence == "medium":
        if "twist region mismatch" in (notes or ""):
            return "twist region — verify"
        return ""
    if bucket == "skip":
        if "end bone" in notes:    return "end bone"
        if "scaffolding" in notes: return "scaffolding"
        if "hair" in notes:        return "hair"
        return "skipped"
    if bucket == "review":
        if "adult" in notes:           return "adult — check manually"
        if "twist region" in notes:    return "twist region — verify"
        if "no matching" in notes:
            cat = notes.split(",")[0].replace("category=", "").strip()
            return f"{cat} — no target"
        if "no target" in notes:       return notes
        if confidence == "medium":     return "low confidence"
        if confidence == "low":        return notes or "needs review"
        return "needs review"
    if bucket == "unmatched":
        return "unmatched"
    if bucket == "missing":
        return ""
    return ""


def _get_target_bones(context):
    """Return sorted list of bone names from the target armature."""
    props = context.scene.bone_remapper
    if props.target_armature and props.target_armature.type == 'ARMATURE':
        return sorted(b.name for b in props.target_armature.data.bones)
    return []


# ---------------------------------------------------------------------------
# Per-row property group
# ---------------------------------------------------------------------------

class BoneMapping(bpy.types.PropertyGroup):
    source:     bpy.props.StringProperty(name="Source")
    target:     bpy.props.StringProperty(name="Target")
    bucket:     bpy.props.StringProperty(name="Bucket")
    confidence: bpy.props.StringProperty(name="Confidence")
    notes:      bpy.props.StringProperty(name="Notes")
    overridden: bpy.props.BoolProperty(name="Overridden", default=False)
    merge_mode: bpy.props.BoolProperty(
        name="Merge weights",
        default=False,
        description="Add this group's weights into the target group instead of renaming",
    )


# ---------------------------------------------------------------------------
# Scene-level properties
# ---------------------------------------------------------------------------

class BoneRemapperProps(bpy.types.PropertyGroup):
    source_mesh: bpy.props.PointerProperty(
        name="Mesh",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH',
    )
    target_armature: bpy.props.PointerProperty(
        name="Armature",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'ARMATURE',
    )
    include_end_bones: bpy.props.BoolProperty(
        name="Include _end bones",
        default=False,
        description="Show terminal _end bones in the mapping list",
    )
    filter_bucket: bpy.props.EnumProperty(
        name="Show",
        items=[
            ('ALL',       "All",       "Show every row"),
            ('REVIEW',    "Review",    "Needs review only"),
            ('UNMATCHED', "Unmatched", "Unmatched only"),
            ('MISSING',   "Missing",   "Target bones with no source group"),
        ],
        default='ALL',
    )
    mappings:        bpy.props.CollectionProperty(type=BoneMapping)
    mapping_index:   bpy.props.IntProperty(default=0)
    stats_matched:   bpy.props.IntProperty(default=0)
    stats_review:    bpy.props.IntProperty(default=0)
    stats_unmatched: bpy.props.IntProperty(default=0)
    stats_skipped:   bpy.props.IntProperty(default=0)
    stats_missing:   bpy.props.IntProperty(default=0)


# ---------------------------------------------------------------------------
# Operator: set target via bone search popup
# ---------------------------------------------------------------------------

class REMAPPER_OT_PickTarget(bpy.types.Operator):
    """Pick a target bone from the armature"""
    bl_idname      = "remapper.pick_target"
    bl_label       = "Pick Target Bone"
    bl_options     = {'REGISTER', 'UNDO'}
    bl_property    = "bone_name"

    row_index: bpy.props.IntProperty()

    def _bone_items(self, context):
        bones = _get_target_bones(context)
        items = [("", "— none —", "")]
        items += [(b, b, "") for b in bones]
        return items

    bone_name: bpy.props.EnumProperty(
        name="Bone",
        items=_bone_items,
    )

    def invoke(self, context, event):
        # Pre-select the current target if one exists
        props = context.scene.bone_remapper
        if 0 <= self.row_index < len(props.mappings):
            current = props.mappings[self.row_index].target
            if current:
                try:
                    self.bone_name = current
                except Exception:
                    pass
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        props = context.scene.bone_remapper
        if 0 <= self.row_index < len(props.mappings):
            row = props.mappings[self.row_index]
            row.target     = self.bone_name
            row.overridden = True

            if self.bone_name:
                # Check if another row already maps to this target
                already_used = any(
                    i != self.row_index and
                    props.mappings[i].target == self.bone_name and
                    props.mappings[i].bucket in ('matched', 'review')
                    for i in range(len(props.mappings))
                )
                row.merge_mode = already_used
                row.bucket     = "matched"
            else:
                row.merge_mode = False
                row.bucket     = "unmatched"
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: pick source vertex group for a missing row
# ---------------------------------------------------------------------------

class REMAPPER_OT_PickSource(bpy.types.Operator):
    """Assign a source vertex group to a missing target bone"""
    bl_idname   = "remapper.pick_source"
    bl_label    = "Pick Source Group"
    bl_options  = {'REGISTER', 'UNDO'}
    bl_property = "group_name"

    row_index: bpy.props.IntProperty()

    def _group_items(self, context):
        props = context.scene.bone_remapper
        items = [("", "— none —", "")]
        if props.source_mesh:
            # Exclude groups already mapped to something
            used = {r.source for r in props.mappings
                    if r.source and r.bucket in ('matched', 'review')}
            for vg in sorted(props.source_mesh.vertex_groups,
                             key=lambda v: v.name):
                label = vg.name
                if vg.name in used:
                    label += "  (already mapped)"
                items.append((vg.name, label, ""))
        return items

    group_name: bpy.props.EnumProperty(
        name="Vertex Group",
        items=_group_items,
    )

    def invoke(self, context, event):
        props = context.scene.bone_remapper
        if 0 <= self.row_index < len(props.mappings):
            current = props.mappings[self.row_index].source
            if current:
                try:
                    self.group_name = current
                except Exception:
                    pass
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        props = context.scene.bone_remapper
        if not (0 <= self.row_index < len(props.mappings)):
            return {'CANCELLED'}

        row = props.mappings[self.row_index]
        row.source     = self.group_name
        row.overridden = True

        if not self.group_name:
            row.bucket = "missing"
            return {'FINISHED'}

        # Check if this source group is already used by another row
        already_used = any(
            i != self.row_index and
            props.mappings[i].source == self.group_name and
            props.mappings[i].bucket in ('matched', 'review')
            for i in range(len(props.mappings))
        )
        row.merge_mode = already_used
        row.bucket     = "review" if already_used else "matched"
        row.confidence = "medium"
        row.notes      = "manually assigned" + (" — merge conflict" if already_used else "")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: Analyse
# ---------------------------------------------------------------------------

class REMAPPER_OT_Analyse(bpy.types.Operator):
    """Run the bone matcher and populate the mapping list"""
    bl_idname  = "remapper.analyse"
    bl_label   = "Analyse"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bone_remapper

        if not props.source_mesh:
            self.report({'ERROR'}, "Select a source mesh first")
            return {'CANCELLED'}
        if not props.target_armature:
            self.report({'ERROR'}, "Select a target armature first")
            return {'CANCELLED'}

        importlib.reload(remapper)

        source_names = [vg.name for vg in props.source_mesh.vertex_groups]
        target_names = [b.name  for b  in props.target_armature.data.bones]
        hierarchy    = {
            b.name: b.parent.name if b.parent else None
            for b in props.target_armature.data.bones
        }

        raw = remapper.match(source_names, target_names, hierarchy)

        props.mappings.clear()
        matched = review = unmatched = skipped = missing = 0

        for m in raw:
            is_end = "end bone" in (m.get("notes") or "")
            if m["bucket"] == "skip" and is_end and not props.include_end_bones:
                skipped += 1
                continue
            if m["bucket"] == "skip" and not is_end:
                skipped += 1
                continue

            row            = props.mappings.add()
            row.source     = m["source"]
            row.target     = m["target"] or ""
            row.bucket     = m["bucket"]
            row.confidence = m["confidence"]
            row.notes      = m.get("notes") or ""

            if   m["bucket"] == "matched":   matched   += 1
            elif m["bucket"] == "review":    review    += 1
            elif m["bucket"] == "unmatched": unmatched += 1
            elif m["bucket"] == "missing":   missing   += 1
            else:                            skipped   += 1

        props.stats_matched   = matched
        props.stats_review    = review
        props.stats_unmatched = unmatched
        props.stats_skipped   = skipped
        props.stats_missing   = missing

        # ---- Write debug log ----
        self._write_debug_log(props, source_names, target_names, raw)

        self.report({'INFO'},
            f"{matched} matched · {review} review · {unmatched} unmatched · {missing} missing")
        return {'FINISHED'}

    def _write_debug_log(self, props, source_names, target_names, raw):
        import datetime
        log_path = os.path.join(
            os.path.dirname(__file__),
            "bone_remapper_debug.txt"
        )
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = []
        lines.append("=" * 72)
        lines.append(f"  VRChat Bone Remapper — Debug Log")
        lines.append(f"  {now}")
        lines.append("=" * 72)
        lines.append("")

        # Setup
        lines.append("── Setup ──────────────────────────────────────────────────────────────")
        lines.append(f"  Source mesh      : {props.source_mesh.name}")
        lines.append(f"  Target armature  : {props.target_armature.name}")
        lines.append(f"  Source vgroups   : {len(source_names)}")
        lines.append(f"  Target bones     : {len(target_names)}")
        lines.append(f"  Include _end     : {props.include_end_bones}")
        lines.append("")

        # Stats
        lines.append("── Results ─────────────────────────────────────────────────────────────")
        lines.append(f"  Matched          : {props.stats_matched}")
        lines.append(f"  Needs review     : {props.stats_review}")
        lines.append(f"  Unmatched        : {props.stats_unmatched}")
        lines.append(f"  Skipped          : {props.stats_skipped}")
        lines.append("")

        # Full mapping table
        lines.append("── Full Mapping Table ───────────────────────────────────────────────────")
        lines.append(f"  {'SOURCE':<35} {'TARGET':<35} {'BUCKET':<12} {'CONF':<8} NOTES")
        lines.append("  " + "-" * 105)
        for m in raw:
            src  = m['source']
            tgt  = m['target'] or "—"
            bkt  = m['bucket']
            conf = m['confidence']
            note = m.get('notes') or ""
            lines.append(f"  {src:<35} {tgt:<35} {bkt:<12} {conf:<8} {note}")
        lines.append("")

        # Normalizer detail — what each source bone tokenized to
        lines.append("── Normalizer Detail (source bones) ─────────────────────────────────────")
        lines.append(f"  {'RAW':<35} {'SIDE':<5} {'IDX':<5} {'TOKENS':<30} {'CATEGORY':<22} {'BUCKET':<12} CONF")
        lines.append("  " + "-" * 120)
        for name in source_names:
            n = remapper.normalize(name)
            c = remapper.classify(n)
            lines.append(
                f"  {n['raw']:<35} "
                f"{str(n['side']):<5} "
                f"{str(n['index']):<5} "
                f"{str(n['tokens']):<30} "
                f"{str(c['category']):<22} "
                f"{c['bucket']:<12} "
                f"{c['confidence']}"
            )
        lines.append("")

        # Target bones — what they classified as
        lines.append("── Normalizer Detail (target bones) ─────────────────────────────────────")
        lines.append(f"  {'RAW':<35} {'SIDE':<5} {'IDX':<5} {'TOKENS':<30} {'CATEGORY':<22} {'BUCKET':<12} CONF")
        lines.append("  " + "-" * 120)
        for name in target_names:
            n = remapper.normalize(name)
            c = remapper.classify(n)
            lines.append(
                f"  {n['raw']:<35} "
                f"{str(n['side']):<5} "
                f"{str(n['index']):<5} "
                f"{str(n['tokens']):<30} "
                f"{str(c['category']):<22} "
                f"{c['bucket']:<12} "
                f"{c['confidence']}"
            )
        lines.append("")

        # Unmatched / review summary for quick scanning
        problem_rows = [m for m in raw if m['bucket'] in ('review', 'unmatched')]
        if problem_rows:
            lines.append("── Needs Attention ──────────────────────────────────────────────────────")
            for m in problem_rows:
                tgt  = m['target'] or "NO TARGET"
                note = m.get('notes') or ""
                lines.append(f"  [{m['bucket'].upper():<9}] {m['source']:<35} → {tgt:<35} {note}")
            lines.append("")

        lines.append("=" * 72)
        lines.append("  End of log")
        lines.append("=" * 72)

        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            self.report({'INFO'}, f"Debug log: {log_path}")
        except Exception as e:
            self.report({'WARNING'}, f"Could not write debug log: {e}")


# ---------------------------------------------------------------------------
# Operator: Apply
# ---------------------------------------------------------------------------

class REMAPPER_OT_Apply(bpy.types.Operator):
    """Rename vertex groups on the source mesh, merging weights where flagged"""
    bl_idname  = "remapper.apply"
    bl_label   = "Apply Remap"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bone_remapper

        if not props.source_mesh:
            self.report({'ERROR'}, "No source mesh")
            return {'CANCELLED'}

        mesh      = props.source_mesh
        renamed   = 0
        merged    = 0
        skipped   = 0
        conflicts = []
        existing  = {vg.name for vg in mesh.vertex_groups}

        for row in props.mappings:
            if row.bucket not in ('matched', 'review'):
                continue
            if not row.target:
                skipped += 1
                continue
            if row.source == row.target and not row.merge_mode:
                continue

            src_vg = mesh.vertex_groups.get(row.source)
            if not src_vg:
                skipped += 1
                continue

            # ---- MERGE MODE ----
            if row.merge_mode:
                tgt_vg = mesh.vertex_groups.get(row.target)
                if not tgt_vg:
                    # Target doesn't exist yet — just rename
                    if row.target in existing and row.target != row.source:
                        conflicts.append(f"{row.source}→{row.target}")
                        skipped += 1
                        continue
                    existing.discard(row.source)
                    existing.add(row.target)
                    src_vg.name = row.target
                    renamed += 1
                    continue

                # Both groups exist — merge src weights into tgt
                self._merge_vertex_groups(mesh, src_vg, tgt_vg)
                mesh.vertex_groups.remove(src_vg)
                merged += 1
                continue

            # ---- RENAME MODE ----
            if row.target in existing and row.target != row.source:
                conflicts.append(f"{row.source}→{row.target}")
                skipped += 1
                continue

            existing.discard(row.source)
            existing.add(row.target)
            src_vg.name = row.target
            renamed += 1

        msg = f"Renamed {renamed}"
        if merged:  msg += f", merged {merged}"
        if skipped: msg += f", skipped {skipped}"
        if conflicts:
            msg += f". Conflicts: {', '.join(conflicts)}"
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)

        return {'FINISHED'}

    @staticmethod
    def _merge_vertex_groups(mesh, src_vg, tgt_vg):
        """
        Add src_vg weights into tgt_vg for every vertex, clamping to [0, 1].
        Vertices only in src get their weight copied straight across.
        """
        src_idx = src_vg.index
        tgt_idx = tgt_vg.index

        for v in mesh.data.vertices:
            src_w = 0.0
            tgt_w = 0.0

            for g in v.groups:
                if g.group == src_idx:
                    src_w = g.weight
                elif g.group == tgt_idx:
                    tgt_w = g.weight

            if src_w == 0.0:
                continue  # nothing to add

            new_w = min(src_w + tgt_w, 1.0)
            tgt_vg.add([v.index], new_w, 'REPLACE')


# ---------------------------------------------------------------------------
# Operator: Reset
# ---------------------------------------------------------------------------

class REMAPPER_OT_Reset(bpy.types.Operator):
    """Clear all mappings and stats"""
    bl_idname  = "remapper.reset"
    bl_label   = "Reset"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.bone_remapper
        props.mappings.clear()
        props.stats_matched   = 0
        props.stats_review    = 0
        props.stats_unmatched = 0
        props.stats_skipped   = 0
        props.stats_missing   = 0
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: Save / Load preset
# ---------------------------------------------------------------------------

class REMAPPER_OT_SavePreset(bpy.types.Operator):
    """Save current mapping to a JSON file"""
    bl_idname  = "remapper.save_preset"
    bl_label   = "Save Preset"
    bl_options = {'REGISTER'}
    filepath:   bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob:bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import json
        props = context.scene.bone_remapper
        data  = [{"source": r.source, "target": r.target}
                 for r in props.mappings if r.target]
        path  = self.filepath if self.filepath.endswith(".json") else self.filepath + ".json"
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        self.report({'INFO'}, f"Saved to {os.path.basename(path)}")
        return {'FINISHED'}


class REMAPPER_OT_LoadPreset(bpy.types.Operator):
    """Load a JSON preset and apply it over the current results"""
    bl_idname   = "remapper.load_preset"
    bl_label    = "Load Preset"
    bl_options  = {'REGISTER', 'UNDO'}
    filepath:    bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        import json
        props = context.scene.bone_remapper
        try:
            with open(self.filepath) as f:
                preset = {item["source"]: item["target"] for item in json.load(f)}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        applied = 0
        for row in props.mappings:
            if row.source in preset:
                row.target     = preset[row.source]
                row.overridden = True
                row.bucket     = "matched"
                applied += 1

        self.report({'INFO'}, f"Applied {applied} preset mappings")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# UI Panel
# ---------------------------------------------------------------------------

_BUCKET_ICON = {
    "matched":   "CHECKMARK",
    "review":    "ERROR",
    "unmatched": "QUESTION",
    "missing":   "GHOST_DISABLED",
    "adult":     "HIDE_OFF",
}
_BUCKET_LABEL = {
    "matched":   "Matched",
    "review":    "Needs Review",
    "unmatched": "Unmatched",
    "missing":   "Missing Source",
    "adult":     "Adult / Custom",
}


class REMAPPER_PT_Main(bpy.types.Panel):
    bl_label       = "Weight Remapper"
    bl_idname      = "REMAPPER_PT_Main"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = "Rigging"

    def draw(self, context):
        props = context.scene.bone_remapper
        l     = self.layout

        # ---- Setup ----
        box = l.box()
        col = box.column(align=True)
        col.prop(props, "source_mesh",     icon='MESH_DATA')
        col.prop(props, "target_armature", icon='ARMATURE_DATA')
        col.prop(props, "include_end_bones", toggle=True)

        # ---- Analyse ----
        row = l.row()
        row.scale_y = 1.3
        row.operator("remapper.analyse", icon='VIEWZOOM')

        total = props.stats_matched + props.stats_review + props.stats_unmatched
        if total == 0:
            return

        # ---- Stats bar ----
        bar = l.box()
        row = bar.row(align=True)
        row.label(text=f"✓ {props.stats_matched}")
        row.label(text=f"⚠ {props.stats_review}")
        row.label(text=f"? {props.stats_unmatched}")
        if props.stats_missing:
            row.label(text=f"◎ {props.stats_missing}")
        if props.stats_skipped:
            row.label(text=f"— {props.stats_skipped}")

        # ---- Filter tabs ----
        l.prop(props, "filter_bucket", expand=True)
        l.separator(factor=0.5)

        # ---- Rows ----
        self._draw_mappings(l, props)

        # ---- Apply / Preset / Reset ----
        l.separator()
        row = l.row(align=True)
        row.scale_y = 1.2
        row.operator("remapper.apply", icon='CHECKMARK', text="Apply Remap")
        row.operator("remapper.save_preset", icon='FILE_TICK', text="")
        row.operator("remapper.load_preset", icon='FILE_FOLDER', text="")
        row.operator("remapper.reset", icon='TRASH', text="")

    # ------------------------------------------------------------------

    def _draw_mappings(self, layout, props):
        fb = props.filter_bucket

        buckets = {"matched": [], "review": [], "unmatched": [],
                   "missing": [], "adult": []}
        for i, row in enumerate(props.mappings):
            b = row.bucket if row.bucket in buckets else "unmatched"
            buckets[b].append((i, row))

        if fb == 'ALL':
            order = ["review", "unmatched", "matched", "missing"]
        elif fb == 'REVIEW':
            order = ["review", "adult"]
        elif fb == 'MISSING':
            order = ["missing"]
        else:
            order = ["unmatched"]

        for bucket_name in order:
            rows = buckets.get(bucket_name, [])
            if not rows:
                continue

            box = layout.box()
            hdr = box.row()
            hdr.label(
                text=f"{_BUCKET_LABEL.get(bucket_name, bucket_name)}  ({len(rows)})",
                icon=_BUCKET_ICON.get(bucket_name, "DOT"),
            )

            for i, row in rows:
                if bucket_name == "missing":
                    self._draw_missing_row(box, i, row)
                else:
                    self._draw_row(box, i, row)

    # ------------------------------------------------------------------

    def _draw_row(self, parent, index, row):
        box = parent.box()
        main = box.row(align=True)

        # Source label
        src_col = main.column(align=True)
        src_col.ui_units_x = 8
        src_col.label(text=row.source, icon='GROUP_VERTEX')

        # Centered arrow
        arr_col = main.column(align=True)
        arr_col.ui_units_x = 1.2
        arr_col.alignment = 'CENTER'
        arr_col.label(text="⊕" if row.merge_mode else "→")

        # Target picker button
        tgt_col = main.column(align=True)
        tgt_col.ui_units_x = 8
        op = tgt_col.operator(
            "remapper.pick_target",
            text=row.target if row.target else "— pick bone —",
            icon='BONE_DATA' if row.target else 'ADD',
        )
        op.row_index = index

        # Merge toggle — only show when a target is set
        if row.target:
            merge_col = main.column(align=True)
            merge_col.ui_units_x = 2
            icon = 'AUTOMERGE_ON' if row.merge_mode else 'AUTOMERGE_OFF'
            merge_col.prop(row, "merge_mode", text="", icon=icon, toggle=True)

        # Short status note
        note = _short_note(row.bucket, row.confidence, row.notes)
        if row.merge_mode:
            note = "merge weights"
        if note:
            note_row = box.row()
            note_row.scale_y = 0.65
            note_row.label(text=f"  {note}", icon='INFO')

    # ------------------------------------------------------------------

    def _draw_missing_row(self, parent, index, row):
        """Flipped layout — target is known, source needs to be assigned."""
        box = parent.box()
        main = box.row(align=True)

        # Source picker (left) — empty until user assigns
        src_col = main.column(align=True)
        src_col.ui_units_x = 8
        op = src_col.operator(
            "remapper.pick_source",
            text=row.source if row.source else "— pick group —",
            icon='GROUP_VERTEX' if row.source else 'ADD',
        )
        op.row_index = index

        # Centered arrow
        arr_col = main.column(align=True)
        arr_col.ui_units_x = 1.2
        arr_col.alignment = 'CENTER'
        arr_col.label(text="→")

        # Target label (right) — fixed, known
        tgt_col = main.column(align=True)
        tgt_col.ui_units_x = 8
        tgt_col.label(text=row.target, icon='BONE_DATA')

        # Note
        note = row.notes or "no source group"
        note_row = box.row()
        note_row.scale_y = 0.65
        note_row.label(text=f"  {note}", icon='INFO')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = [
    BoneMapping,
    BoneRemapperProps,
    REMAPPER_OT_PickTarget,
    REMAPPER_OT_PickSource,
    REMAPPER_OT_Analyse,
    REMAPPER_OT_Apply,
    REMAPPER_OT_Reset,
    REMAPPER_OT_SavePreset,
    REMAPPER_OT_LoadPreset,
    REMAPPER_PT_Main,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bone_remapper = bpy.props.PointerProperty(type=BoneRemapperProps)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.bone_remapper


if __name__ == "__main__":
    register()
