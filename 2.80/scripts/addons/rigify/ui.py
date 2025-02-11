#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

# <pep8 compliant>

import bpy
from bpy.props import (
    BoolProperty,
    IntProperty,
    EnumProperty,
    StringProperty
)

from mathutils import Color

from .utils import MetarigError
from .utils import write_metarig, write_widget
from .utils import unique_name
from .utils import upgradeMetarigTypes, outdated_types
from .utils import get_keyed_frames, bones_in_frame
from .utils import overwrite_prop_animation
from .rigs.utils import get_limb_generated_names
from . import rig_lists
from . import generate
from . import rot_mode
from . import feature_set_list


def build_type_list(context, rigify_types):
    rigify_types.clear()

    for r in sorted(rig_lists.rigs):
        if (context.object.data.active_feature_set in ('all', rig_lists.rigs[r]['feature_set'])
                or len(feature_set_list.feature_set_items(context.scene, context)) == 2
                ):
            a = rigify_types.add()
            a.name = r


class DATA_PT_rigify_buttons(bpy.types.Panel):
    bl_label = "Rigify Buttons"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and context.active_object.data.get("rig_id") is None

    def draw(self, context):
        C = context
        layout = self.layout
        obj = context.object
        id_store = C.window_manager

        if obj.mode in {'POSE', 'OBJECT'}:

            WARNING = "Warning: Some features may change after generation"
            show_warning = False
            show_update_metarig = False
            show_not_updatable = False

            check_props = ['IK_follow', 'root/parent', 'FK_limb_follow', 'IK_Stretch']

            for bone in obj.pose.bones:
                if bone.bone.layers[30] and (list(set(bone.keys()) & set(check_props))):
                    show_warning = True
                    break
            for b in obj.pose.bones:
                if b.rigify_type in outdated_types.keys():
                    if outdated_types[b.rigify_type]:
                        show_update_metarig = True
                    else:
                        show_update_metarig = False
                        show_not_updatable = True
                        break

            if show_warning:
                layout.label(text=WARNING, icon='ERROR')

            if show_not_updatable:
                layout.label(text="WARNING: This metarig contains deprecated rigify rig-types and cannot be upgraded automatically.", icon='ERROR')
                layout.label(text="If you want to use it anyway try enabling the legacy mode before generating again.")

                layout.operator("pose.rigify_switch_to_legacy", text="Switch to Legacy")

            enable_generate_and_advanced = not (show_not_updatable or show_update_metarig)

            if show_update_metarig:

                layout.label(text="This metarig contains old rig-types that can be automatically upgraded to benefit of rigify's new features.", icon='ERROR')
                layout.label(text="To use it as-is you need to enable legacy mode.",)
                layout.operator("pose.rigify_upgrade_types", text="Upgrade Metarig")

            row = layout.row()
            # Rig type field

            col = layout.column(align=True)
            col.active = (not 'rig_id' in C.object.data)

            col.separator()
            row = col.row()
            row.operator("pose.rigify_generate", text="Generate Rig", icon='POSE_HLT')

            row.enabled = enable_generate_and_advanced

            if id_store.rigify_advanced_generation:
                icon = 'UNLOCKED'
            else:
                icon = 'LOCKED'

            col = layout.column()
            col.enabled = enable_generate_and_advanced
            row = col.row()
            row.prop(id_store, "rigify_advanced_generation", toggle=True, icon=icon)

            if id_store.rigify_advanced_generation:

                row = col.row(align=True)
                row.prop(id_store, "rigify_generate_mode", expand=True)

                main_row = col.row(align=True).split(factor=0.3)
                col1 = main_row.column()
                col2 = main_row.column()
                col1.label(text="Rig Name")
                row = col1.row()
                row.label(text="Target Rig")
                row.enabled = (id_store.rigify_generate_mode == "overwrite")
                row = col1.row()
                row.label(text="Target UI")
                row.enabled = (id_store.rigify_generate_mode == "overwrite")

                row = col2.row(align=True)
                row.prop(id_store, "rigify_rig_basename", text="", icon="SORTALPHA")

                row = col2.row(align=True)
                for i in range(0, len(id_store.rigify_target_rigs)):
                    id_store.rigify_target_rigs.remove(0)

                for ob in context.scene.objects:
                    if type(ob.data) == bpy.types.Armature and "rig_id" in ob.data:
                        id_store.rigify_target_rigs.add()
                        id_store.rigify_target_rigs[-1].name = ob.name

                row.prop_search(id_store, "rigify_target_rig", id_store, "rigify_target_rigs", text="",
                                icon='OUTLINER_OB_ARMATURE')
                row.enabled = (id_store.rigify_generate_mode == "overwrite")

                for i in range(0, len(id_store.rigify_rig_uis)):
                    id_store.rigify_rig_uis.remove(0)

                for t in bpy.data.texts:
                    id_store.rigify_rig_uis.add()
                    id_store.rigify_rig_uis[-1].name = t.name

                row = col2.row()
                row.prop_search(id_store, "rigify_rig_ui", id_store, "rigify_rig_uis", text="", icon='TEXT')
                row.enabled = (id_store.rigify_generate_mode == "overwrite")

                row = col.row()
                row.prop(id_store, "rigify_force_widget_update")
                if id_store.rigify_generate_mode == 'new':
                    row.enabled = False

        elif obj.mode == 'EDIT':
            # Build types list
            build_type_list(context, id_store.rigify_types)

            if id_store.rigify_active_type > len(id_store.rigify_types):
                id_store.rigify_active_type = 0

            # Rig type list
            if len(feature_set_list.feature_set_items(context.scene, context)) > 2:
                row = layout.row()
                row.prop(context.object.data, "active_feature_set")
            row = layout.row()
            row.template_list("UI_UL_list", "rigify_types", id_store, "rigify_types", id_store, 'rigify_active_type')

            props = layout.operator("armature.metarig_sample_add", text="Add sample")
            props.metarig_type = id_store.rigify_types[id_store.rigify_active_type].name


class DATA_PT_rigify_layer_names(bpy.types.Panel):
    bl_label = "Rigify Layer Names"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and context.active_object.data.get("rig_id") is None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        arm = obj.data

        # Ensure that the layers exist
        if 0:
            for i in range(1 + len(arm.rigify_layers), 29):
                arm.rigify_layers.add()
        else:
            # Can't add while drawing, just use button
            if len(arm.rigify_layers) < 29:
                layout.operator("pose.rigify_layer_init")
                return

        # UI
        main_row = layout.row(align=True).split(factor=0.05)
        col1 = main_row.column()
        col2 = main_row.column()
        col1.label()
        for i in range(32):
            if i == 16 or i == 29:
                col1.label()
            col1.label(text=str(i+1) + '.')

        for i, rigify_layer in enumerate(arm.rigify_layers):
            # note: rigify_layer == arm.rigify_layers[i]
            if (i % 16) == 0:
                col = col2.column()
                if i == 0:
                    col.label(text="Top Row:")
                else:
                    col.label(text="Bottom Row:")
            if (i % 8) == 0:
                col = col2.column()
            if i != 28:
                row = col.row(align=True)
                icon = 'RESTRICT_VIEW_OFF' if arm.layers[i] else 'RESTRICT_VIEW_ON'
                row.prop(arm, "layers", index=i, text="", toggle=True, icon=icon)
                #row.prop(arm, "layers", index=i, text="Layer %d" % (i + 1), toggle=True, icon=icon)
                row.prop(rigify_layer, "name", text="")
                row.prop(rigify_layer, "row", text="UI Row")
                icon = 'RADIOBUT_ON' if rigify_layer.selset else 'RADIOBUT_OFF'
                row.prop(rigify_layer, "selset", text="", toggle=True, icon=icon)
                row.prop(rigify_layer, "group", text="Bone Group")
            else:
                row = col.row(align=True)

                icon = 'RESTRICT_VIEW_OFF' if arm.layers[i] else 'RESTRICT_VIEW_ON'
                row.prop(arm, "layers", index=i, text="", toggle=True, icon=icon)
                # row.prop(arm, "layers", index=i, text="Layer %d" % (i + 1), toggle=True, icon=icon)
                row1 = row.split(align=True).row(align=True)
                row1.prop(rigify_layer, "name", text="")
                row1.prop(rigify_layer, "row", text="UI Row")
                row1.enabled = False
                icon = 'RADIOBUT_ON' if rigify_layer.selset else 'RADIOBUT_OFF'
                row.prop(rigify_layer, "selset", text="", toggle=True, icon=icon)
                row.prop(rigify_layer, "group", text="Bone Group")
            if rigify_layer.group == 0:
                row.label(text='None')
            else:
                row.label(text=arm.rigify_colors[rigify_layer.group-1].name)

        col = col2.column()
        col.label(text="Reserved:")
        # reserved_names = {28: 'Root', 29: 'DEF', 30: 'MCH', 31: 'ORG'}
        reserved_names = {29: 'DEF', 30: 'MCH', 31: 'ORG'}
        # for i in range(28, 32):
        for i in range(29, 32):
            row = col.row(align=True)
            icon = 'RESTRICT_VIEW_OFF' if arm.layers[i] else 'RESTRICT_VIEW_ON'
            row.prop(arm, "layers", index=i, text="", toggle=True, icon=icon)
            row.label(text=reserved_names[i])


class DATA_OT_rigify_add_bone_groups(bpy.types.Operator):
    bl_idname = "armature.rigify_add_bone_groups"
    bl_label = "Rigify Add Standard Bone Groups"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'rigify_colors'):
            return {'FINISHED'}

        groups = ['Root', 'IK', 'Special', 'Tweak', 'FK', 'Extra']

        for g in groups:
            if g in armature.rigify_colors.keys():
                continue

            armature.rigify_colors.add()
            armature.rigify_colors[-1].name = g

            armature.rigify_colors[g].select = Color((0.3140000104904175, 0.7839999794960022, 1.0))
            armature.rigify_colors[g].active = Color((0.5490000247955322, 1.0, 1.0))
            armature.rigify_colors[g].standard_colors_lock = True

            if g == "Root":
                armature.rigify_colors[g].normal = Color((0.43529415130615234, 0.18431372940540314, 0.41568630933761597))
            if g == "IK":
                armature.rigify_colors[g].normal = Color((0.6039215922355652, 0.0, 0.0))
            if g== "Special":
                armature.rigify_colors[g].normal = Color((0.9568628072738647, 0.7882353663444519, 0.0470588281750679))
            if g== "Tweak":
                armature.rigify_colors[g].normal = Color((0.03921568766236305, 0.21176472306251526, 0.5803921818733215))
            if g== "FK":
                armature.rigify_colors[g].normal = Color((0.11764706671237946, 0.5686274766921997, 0.03529411926865578))
            if g== "Extra":
                armature.rigify_colors[g].normal = Color((0.9686275124549866, 0.250980406999588, 0.0941176563501358))

        return {'FINISHED'}


class DATA_OT_rigify_use_standard_colors(bpy.types.Operator):
    bl_idname = "armature.rigify_use_standard_colors"
    bl_label = "Rigify Get active/select colors from current theme"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'rigify_colors'):
            return {'FINISHED'}

        current_theme = bpy.context.preferences.themes.items()[0][0]
        theme = bpy.context.preferences.themes[current_theme]

        armature.rigify_selection_colors.select = theme.view_3d.bone_pose
        armature.rigify_selection_colors.active = theme.view_3d.bone_pose_active

        # for col in armature.rigify_colors:
        #     col.select = theme.view_3d.bone_pose
        #     col.active = theme.view_3d.bone_pose_active

        return {'FINISHED'}


class DATA_OT_rigify_apply_selection_colors(bpy.types.Operator):
    bl_idname = "armature.rigify_apply_selection_colors"
    bl_label = "Rigify Apply user defined active/select colors"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data
        if not hasattr(armature, 'rigify_colors'):
            return {'FINISHED'}

        #current_theme = bpy.context.preferences.themes.items()[0][0]
        #theme = bpy.context.preferences.themes[current_theme]

        for col in armature.rigify_colors:
            col.select = armature.rigify_selection_colors.select
            col.active = armature.rigify_selection_colors.active

        return {'FINISHED'}


class DATA_OT_rigify_bone_group_add(bpy.types.Operator):
    bl_idname = "armature.rigify_bone_group_add"
    bl_label = "Rigify Add Bone Group color set"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data

        if hasattr(armature, 'rigify_colors'):
            armature.rigify_colors.add()
            armature.rigify_colors[-1].name = unique_name(armature.rigify_colors, 'Group')

            current_theme = bpy.context.preferences.themes.items()[0][0]
            theme = bpy.context.preferences.themes[current_theme]

            armature.rigify_colors[-1].normal = theme.view_3d.wire
            armature.rigify_colors[-1].normal.hsv = theme.view_3d.wire.hsv
            armature.rigify_colors[-1].select = theme.view_3d.bone_pose
            armature.rigify_colors[-1].select.hsv = theme.view_3d.bone_pose.hsv
            armature.rigify_colors[-1].active = theme.view_3d.bone_pose_active
            armature.rigify_colors[-1].active.hsv = theme.view_3d.bone_pose_active.hsv

        return {'FINISHED'}


class DATA_OT_rigify_bone_group_add_theme(bpy.types.Operator):
    bl_idname = "armature.rigify_bone_group_add_theme"
    bl_label = "Rigify Add Bone Group color set from Theme"
    bl_options = {"REGISTER", "UNDO"}

    theme: EnumProperty(items=(
        ('THEME01', 'THEME01', ''),
        ('THEME02', 'THEME02', ''),
        ('THEME03', 'THEME03', ''),
        ('THEME04', 'THEME04', ''),
        ('THEME05', 'THEME05', ''),
        ('THEME06', 'THEME06', ''),
        ('THEME07', 'THEME07', ''),
        ('THEME08', 'THEME08', ''),
        ('THEME09', 'THEME09', ''),
        ('THEME10', 'THEME10', ''),
        ('THEME11', 'THEME11', ''),
        ('THEME12', 'THEME12', ''),
        ('THEME13', 'THEME13', ''),
        ('THEME14', 'THEME14', ''),
        ('THEME15', 'THEME15', ''),
        ('THEME16', 'THEME16', ''),
        ('THEME17', 'THEME17', ''),
        ('THEME18', 'THEME18', ''),
        ('THEME19', 'THEME19', ''),
        ('THEME20', 'THEME20', '')
        ),
         name='Theme')

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        armature = obj.data

        if hasattr(armature, 'rigify_colors'):

            if self.theme in armature.rigify_colors.keys():
                return {'FINISHED'}
            armature.rigify_colors.add()
            armature.rigify_colors[-1].name = self.theme

            id = int(self.theme[-2:]) - 1

            theme_color_set = bpy.context.preferences.themes[0].bone_color_sets[id]

            armature.rigify_colors[-1].normal = theme_color_set.normal
            armature.rigify_colors[-1].select = theme_color_set.select
            armature.rigify_colors[-1].active = theme_color_set.active

        return {'FINISHED'}


class DATA_OT_rigify_bone_group_remove(bpy.types.Operator):
    bl_idname = "armature.rigify_bone_group_remove"
    bl_label = "Rigify Remove Bone Group color set"

    idx: IntProperty()

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object
        obj.data.rigify_colors.remove(self.idx)

        # set layers references to 0
        for l in obj.data.rigify_layers:
            if l.group == self.idx + 1:
                l.group = 0
            elif l.group > self.idx + 1:
                l.group -= 1

        return {'FINISHED'}


class DATA_OT_rigify_bone_group_remove_all(bpy.types.Operator):
    bl_idname = "armature.rigify_bone_group_remove_all"
    bl_label = "Rigify Remove All Bone Groups"

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE'

    def execute(self, context):
        obj = context.object

        for i, col in enumerate(obj.data.rigify_colors):
            obj.data.rigify_colors.remove(0)
            # set layers references to 0
            for l in obj.data.rigify_layers:
                if l.group == i + 1:
                    l.group = 0

        return {'FINISHED'}


class DATA_UL_rigify_bone_groups(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row = row.split(factor=0.1)
        row.label(text=str(index+1))
        row = row.split(factor=0.7)
        row.prop(item, "name", text='', emboss=False)
        row = row.row(align=True)
        icon = 'LOCKED' if item.standard_colors_lock else 'UNLOCKED'
        #row.prop(item, "standard_colors_lock", text='', icon=icon)
        row.prop(item, "normal", text='')
        row2 = row.row(align=True)
        row2.prop(item, "select", text='')
        row2.prop(item, "active", text='')
        #row2.enabled = not item.standard_colors_lock
        row2.enabled = not bpy.context.object.data.rigify_colors_lock


class DATA_MT_rigify_bone_groups_context_menu(bpy.types.Menu):
    bl_label = 'Rigify Bone Groups Specials'

    def draw(self, context):
        layout = self.layout

        layout.operator('armature.rigify_bone_group_remove_all')


class DATA_PT_rigify_bone_groups(bpy.types.Panel):
    bl_label = "Rigify Bone Groups"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "data"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and context.active_object.data.get("rig_id") is None

    def draw(self, context):
        obj = context.object
        armature = obj.data
        color_sets = obj.data.rigify_colors
        idx = obj.data.rigify_colors_index

        layout = self.layout
        row = layout.row()
        row.operator("armature.rigify_use_standard_colors", icon='FILE_REFRESH', text='')
        row = row.row(align=True)
        row.prop(armature.rigify_selection_colors, 'select', text='')
        row.prop(armature.rigify_selection_colors, 'active', text='')
        row = layout.row(align=True)
        icon = 'LOCKED' if armature.rigify_colors_lock else 'UNLOCKED'
        row.prop(armature, 'rigify_colors_lock', text = 'Unified select/active colors', icon=icon)
        row.operator("armature.rigify_apply_selection_colors", icon='FILE_REFRESH', text='Apply')
        row = layout.row()
        row.template_list("DATA_UL_rigify_bone_groups", "", obj.data, "rigify_colors", obj.data, "rigify_colors_index")

        col = row.column(align=True)
        col.operator("armature.rigify_bone_group_add", icon='ZOOM_IN', text="")
        col.operator("armature.rigify_bone_group_remove", icon='ZOOM_OUT', text="").idx = obj.data.rigify_colors_index
        col.menu("DATA_MT_rigify_bone_groups_context_menu", icon='DOWNARROW_HLT', text="")
        row = layout.row()
        row.prop(armature, 'rigify_theme_to_add', text = 'Theme')
        op = row.operator("armature.rigify_bone_group_add_theme", text="Add From Theme")
        op.theme = armature.rigify_theme_to_add
        row = layout.row()
        row.operator("armature.rigify_add_bone_groups", text="Add Standard")


class BONE_PT_rigify_buttons(bpy.types.Panel):
    bl_label = "Rigify Type"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "bone"
    #bl_options = {'DEFAULT_OPEN'}

    @classmethod
    def poll(cls, context):

        return context.object.type == 'ARMATURE' and context.active_pose_bone\
               and context.active_object.data.get("rig_id") is None

    def draw(self, context):
        C = context
        id_store = C.window_manager
        bone = context.active_pose_bone
        rig_name = str(context.active_pose_bone.rigify_type).replace(" ", "")

        layout = self.layout

        # Build types list
        build_type_list(context, id_store.rigify_types)

        # Rig type field
        if len(feature_set_list.feature_set_items(context.scene, context)) > 2:
            row = layout.row()
            row.prop(context.object.data, "active_feature_set")
        row = layout.row()
        row.prop_search(bone, "rigify_type", id_store, "rigify_types", text="Rig type")

        # Rig type parameters / Rig type non-exist alert
        if rig_name != "":
            try:
                rig = rig_lists.rigs[rig_name]['module']
            except (ImportError, AttributeError):
                row = layout.row()
                box = row.box()
                box.label(text="ALERT: type \"%s\" does not exist!" % rig_name)
            else:
                try:
                    rig.parameters_ui
                except AttributeError:
                    col = layout.column()
                    col.label(text="No options")
                else:
                    col = layout.column()
                    col.label(text="Options:")
                    box = layout.box()
                    rig.parameters_ui(box, bone.rigify_parameters)


class VIEW3D_PT_tools_rigify_dev(bpy.types.Panel):
    bl_label = "Rigify Dev Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'

    @classmethod
    def poll(cls, context):
        return context.mode in ['EDIT_ARMATURE', 'EDIT_MESH']

    @classmethod
    def poll(cls, context):
        return context.mode in ['EDIT_ARMATURE', 'EDIT_MESH']

    def draw(self, context):
        obj = context.active_object
        if obj is not None:
            if context.mode == 'EDIT_ARMATURE':
                r = self.layout.row()
                r.operator("armature.rigify_encode_metarig", text="Encode Metarig to Python")
                r = self.layout.row()
                r.operator("armature.rigify_encode_metarig_sample", text="Encode Sample to Python")

            if context.mode == 'EDIT_MESH':
                r = self.layout.row()
                r.operator("mesh.rigify_encode_mesh_widget", text="Encode Mesh Widget to Python")


class VIEW3D_PT_rigify_animation_tools(bpy.types.Panel):
    bl_label = "Rigify Animation Tools"
    bl_context = "posemode"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'View'

    @classmethod
    def poll(cls, context):
        return context.object.type == 'ARMATURE' and context.active_object.data.get("rig_id") is not None

    def draw(self, context):
        obj = context.active_object
        id_store = context.window_manager
        if obj is not None:
            row = self.layout.row()

            if id_store.rigify_transfer_only_selected:
                icon = 'OUTLINER_DATA_ARMATURE'
            else:
                icon = 'ARMATURE_DATA'

            row.prop(id_store, 'rigify_transfer_only_selected', toggle=True, icon=icon)

            row = self.layout.row(align=True)
            row.operator("rigify.ik2fk", text='IK2FK Pose', icon='SNAP_ON')
            row.operator("rigify.fk2ik", text='FK2IK Pose', icon='SNAP_ON')

            row = self.layout.row(align=True)
            row.operator("rigify.transfer_fk_to_ik", text='IK2FK Action', icon='ACTION_TWEAK')
            row.operator("rigify.transfer_ik_to_fk", text='FK2IK Action', icon='ACTION_TWEAK')

            row = self.layout.row(align=True)
            row.operator("rigify.clear_animation", text="Clear IK Action", icon='CANCEL').anim_type = "IK"
            row.operator("rigify.clear_animation", text="Clear FK Action", icon='CANCEL').anim_type = "FK"

            row = self.layout.row(align=True)
            op = row.operator("rigify.rotation_pole", icon='FORCE_HARMONIC', text='Switch to pole')
            op.value = True
            op.toggle = False
            op.bake = True
            op = row.operator("rigify.rotation_pole", icon='FORCE_MAGNETIC', text='Switch to rotation')
            op.value = False
            op.toggle = False
            op.bake = True
            row = self.layout.row(align=True)
            row.prop(id_store, 'rigify_transfer_start_frame')
            row.prop(id_store, 'rigify_transfer_end_frame')
            row.operator("rigify.get_frame_range", icon='TIME', text='')


def rigify_report_exception(operator, exception):
    import traceback
    import sys
    import os
    # find the module name where the error happened
    # hint, this is the metarig type!
    exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
    fn = traceback.extract_tb(exceptionTraceback)[-1][0]
    fn = os.path.basename(fn)
    fn = os.path.splitext(fn)[0]
    message = []
    if fn.startswith("__"):
        message.append("Incorrect armature...")
    else:
        message.append("Incorrect armature for type '%s'" % fn)
    message.append(exception.message)

    message.reverse()  # XXX - stupid! menu's are upside down!

    operator.report({'INFO'}, '\n'.join(message))


class LayerInit(bpy.types.Operator):
    """Initialize armature rigify layers"""

    bl_idname = "pose.rigify_layer_init"
    bl_label = "Add Rigify Layers"
    bl_options = {'UNDO', 'INTERNAL'}

    def execute(self, context):
        obj = context.object
        arm = obj.data
        for i in range(1 + len(arm.rigify_layers), 30):
            arm.rigify_layers.add()
        arm.rigify_layers[28].name = 'Root'
        arm.rigify_layers[28].row = 14
        return {'FINISHED'}


class Generate(bpy.types.Operator):
    """Generates a rig from the active metarig armature"""

    bl_idname = "pose.rigify_generate"
    bl_label = "Rigify Generate Rig"
    bl_options = {'UNDO', 'INTERNAL'}
    bl_description = 'Generates a rig from the active metarig armature'

    def execute(self, context):
        import importlib
        importlib.reload(generate)

        try:
            generate.generate_rig(context, context.object)
        except MetarigError as rig_exception:
            rigify_report_exception(self, rig_exception)

        return {'FINISHED'}


class UpgradeMetarigTypes(bpy.types.Operator):
    """Upgrades metarig bones rigify_types"""

    bl_idname = "pose.rigify_upgrade_types"
    bl_label = "Rigify Upgrade Metarig Types"
    bl_description = 'Upgrades the rigify types on the active metarig armature'
    bl_options = {'UNDO'}

    def execute(self, context):
        for obj in bpy.data.objects:
            if type(obj.data) == bpy.types.Armature:
                upgradeMetarigTypes(obj)
        return {'FINISHED'}


class SwitchToLegacy(bpy.types.Operator):
    """Switch to Legacy mode"""

    bl_idname = "pose.rigify_switch_to_legacy"
    bl_label = "Legacy Mode will disable Rigify new features"
    bl_description = 'Switches Rigify to Legacy Mode'
    bl_options = {'UNDO', 'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        bpy.context.preferences.addons['rigify'].preferences.legacy_mode = True
        return {'FINISHED'}


class Sample(bpy.types.Operator):
    """Create a sample metarig to be modified before generating the final rig"""

    bl_idname = "armature.metarig_sample_add"
    bl_label = "Add a sample metarig for a rig type"
    bl_options = {'UNDO', 'INTERNAL'}

    metarig_type: StringProperty(
        name="Type",
        description="Name of the rig type to generate a sample of",
        maxlen=128,
    )

    def execute(self, context):
        if context.mode == 'EDIT_ARMATURE' and self.metarig_type != "":
            try:
                rig = rig_lists.rigs[self.metarig_type]["module"]
                create_sample = rig.create_sample
            except (ImportError, AttributeError):
                raise Exception("rig type '" + self.metarig_type + "' has no sample.")
            else:
                create_sample(context.active_object)
            finally:
                bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeMetarig(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig.
    """
    bl_idname = "armature.rigify_encode_metarig"
    bl_label = "Rigify Encode Metarig"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_ARMATURE'

    def execute(self, context):
        name = "metarig.py"

        if name in bpy.data.texts:
            text_block = bpy.data.texts[name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name)

        text = write_metarig(context.active_object, layers=True, func_name="create", groups=True)
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeMetarigSample(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig
        as a sample.
    """
    bl_idname = "armature.rigify_encode_metarig_sample"
    bl_label = "Rigify Encode Metarig Sample"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_ARMATURE'

    def execute(self, context):
        name = "metarig_sample.py"

        if name in bpy.data.texts:
            text_block = bpy.data.texts[name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name)

        text = write_metarig(context.active_object, layers=False, func_name="create_sample")
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class EncodeWidget(bpy.types.Operator):
    """ Creates Python code that will generate the selected metarig.
    """
    bl_idname = "mesh.rigify_encode_mesh_widget"
    bl_label = "Rigify Encode Widget"
    bl_options = {'UNDO'}

    @classmethod
    def poll(self, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        name = "widget.py"

        if name in bpy.data.texts:
            text_block = bpy.data.texts[name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(name)

        text = write_widget(context.active_object)
        text_block.write(text)
        bpy.ops.object.mode_set(mode='EDIT')

        return {'FINISHED'}


class OBJECT_OT_GetFrameRange(bpy.types.Operator):
    """Get start and end frame range"""
    bl_idname = "rigify.get_frame_range"
    bl_label = "Get Frame Range"

    def execute(self, context):
        scn = context.scene
        id_store = context.window_manager

        id_store.rigify_transfer_start_frame = scn.frame_start
        id_store.rigify_transfer_end_frame = scn.frame_end

        return {'FINISHED'}


def FktoIk(rig, window='ALL'):

    scn = bpy.context.scene
    id_store = bpy.context.window_manager

    rig_id = rig.data['rig_id']
    leg_ik2fk = eval('bpy.ops.pose.rigify_leg_ik2fk_' + rig_id)
    arm_ik2fk = eval('bpy.ops.pose.rigify_arm_ik2fk_' + rig_id)
    limb_generated_names = get_limb_generated_names(rig)

    if window == 'ALL':
        frames = get_keyed_frames(rig)
        frames = [f for f in frames if f in range(id_store.rigify_transfer_start_frame, id_store.rigify_transfer_end_frame+1)]
    elif window == 'CURRENT':
        frames = [scn.frame_current]
    else:
        frames = [scn.frame_current]

    if not id_store.rigify_transfer_only_selected:
        pbones = rig.pose.bones
        bpy.ops.pose.select_all(action='DESELECT')
    else:
        pbones = bpy.context.selected_pose_bones
        bpy.ops.pose.select_all(action='DESELECT')

    for b in pbones:
        for group in limb_generated_names:
            if b.name in limb_generated_names[group].values() or b.name in limb_generated_names[group]['controls']\
                    or b.name in limb_generated_names[group]['ik_ctrl']:
                names = limb_generated_names[group]
                if names['limb_type'] == 'arm':
                    func = arm_ik2fk
                    controls = names['controls']
                    ik_ctrl = names['ik_ctrl']
                    fk_ctrl = names['fk_ctrl']
                    parent = names['parent']
                    pole = names['pole']
                    rig.pose.bones[controls[0]].bone.select = True
                    rig.pose.bones[controls[4]].bone.select = True
                    rig.pose.bones[pole].bone.select = True
                    rig.pose.bones[parent].bone.select = True
                    kwargs = {'uarm_fk': controls[1], 'farm_fk': controls[2], 'hand_fk': controls[3],
                              'uarm_ik': controls[0], 'farm_ik': ik_ctrl[1], 'hand_ik': controls[4],
                              'pole': pole, 'main_parent': parent}
                    args = (controls[0], controls[1], controls[2], controls[3],
                            controls[4], pole, parent)
                else:
                    func = leg_ik2fk
                    controls = names['controls']
                    ik_ctrl = names['ik_ctrl']
                    fk_ctrl = names['fk_ctrl']
                    parent = names['parent']
                    pole = names['pole']
                    rig.pose.bones[controls[0]].bone.select = True
                    rig.pose.bones[controls[6]].bone.select = True
                    rig.pose.bones[controls[5]].bone.select = True
                    rig.pose.bones[pole].bone.select = True
                    rig.pose.bones[parent].bone.select = True
                    kwargs = {'thigh_fk': controls[1], 'shin_fk': controls[2], 'foot_fk': controls[3],
                              'mfoot_fk': controls[7], 'thigh_ik': controls[0], 'shin_ik': ik_ctrl[1],
                              'foot_ik': controls[6], 'pole': pole, 'footroll': controls[5], 'mfoot_ik': ik_ctrl[2],
                              'main_parent': parent}
                    args = (controls[0], controls[1], controls[2], controls[3],
                            controls[6], controls[5], pole, parent)

                for f in frames:
                    if not bones_in_frame(f, rig, *args):
                        continue
                    scn.frame_set(f)
                    func(**kwargs)
                    bpy.ops.anim.keyframe_insert_menu(type='BUILTIN_KSI_VisualLocRot')
                    bpy.ops.anim.keyframe_insert_menu(type='Scaling')

                bpy.ops.pose.select_all(action='DESELECT')
                limb_generated_names.pop(group)
                break


def IktoFk(rig, window='ALL'):

    scn = bpy.context.scene
    id_store = bpy.context.window_manager

    rig_id = rig.data['rig_id']
    leg_fk2ik = eval('bpy.ops.pose.rigify_leg_fk2ik_' + rig_id)
    arm_fk2ik = eval('bpy.ops.pose.rigify_arm_fk2ik_' + rig_id)
    limb_generated_names = get_limb_generated_names(rig)

    if window == 'ALL':
        frames = get_keyed_frames(rig)
        frames = [f for f in frames if f in range(id_store.rigify_transfer_start_frame, id_store.rigify_transfer_end_frame+1)]
    elif window == 'CURRENT':
        frames = [scn.frame_current]
    else:
        frames = [scn.frame_current]

    if not id_store.rigify_transfer_only_selected:
        bpy.ops.pose.select_all(action='DESELECT')
        pbones = rig.pose.bones
    else:
        pbones = bpy.context.selected_pose_bones
        bpy.ops.pose.select_all(action='DESELECT')

    for b in pbones:
        for group in limb_generated_names:
            if b.name in limb_generated_names[group].values() or b.name in limb_generated_names[group]['controls']\
                    or b.name in limb_generated_names[group]['ik_ctrl']:
                names = limb_generated_names[group]
                if names['limb_type'] == 'arm':
                    func = arm_fk2ik
                    controls = names['controls']
                    ik_ctrl = names['ik_ctrl']
                    fk_ctrl = names['fk_ctrl']
                    parent = names['parent']
                    pole = names['pole']
                    rig.pose.bones[controls[1]].bone.select = True
                    rig.pose.bones[controls[2]].bone.select = True
                    rig.pose.bones[controls[3]].bone.select = True
                    kwargs = {'uarm_fk': controls[1], 'farm_fk': controls[2], 'hand_fk': controls[3],
                              'uarm_ik': controls[0], 'farm_ik': ik_ctrl[1],
                              'hand_ik': controls[4]}
                    args = (controls[0], controls[1], controls[2], controls[3],
                            controls[4], pole, parent)
                else:
                    func = leg_fk2ik
                    controls = names['controls']
                    ik_ctrl = names['ik_ctrl']
                    fk_ctrl = names['fk_ctrl']
                    parent = names['parent']
                    pole = names['pole']
                    rig.pose.bones[controls[1]].bone.select = True
                    rig.pose.bones[controls[2]].bone.select = True
                    rig.pose.bones[controls[3]].bone.select = True
                    kwargs = {'thigh_fk': controls[1], 'shin_fk': controls[2], 'foot_fk': controls[3],
                              'mfoot_fk': controls[7], 'thigh_ik': controls[0], 'shin_ik': ik_ctrl[1],
                              'foot_ik': ik_ctrl[2], 'mfoot_ik': ik_ctrl[2]}
                    args = (controls[0], controls[1], controls[2], controls[3],
                            controls[6], controls[5], pole, parent)

                for f in frames:
                    if not bones_in_frame(f, rig, *args):
                        continue
                    scn.frame_set(f)
                    func(**kwargs)
                    bpy.ops.anim.keyframe_insert_menu(type='BUILTIN_KSI_VisualLocRot')
                    bpy.ops.anim.keyframe_insert_menu(type='Scaling')

                bpy.ops.pose.select_all(action='DESELECT')
                limb_generated_names.pop(group)
                break


def clearAnimation(act, anim_type, names):

    bones = []
    for group in names:
        if names[group]['limb_type'] == 'arm':
            if anim_type == 'IK':
                bones.extend([names[group]['controls'][0], names[group]['controls'][4]])
            elif anim_type == 'FK':
                bones.extend([names[group]['controls'][1], names[group]['controls'][2], names[group]['controls'][3]])
        else:
            if anim_type == 'IK':
                bones.extend([names[group]['controls'][0], names[group]['controls'][6], names[group]['controls'][5],
                              names[group]['controls'][4]])
            elif anim_type == 'FK':
                bones.extend([names[group]['controls'][1], names[group]['controls'][2], names[group]['controls'][3],
                              names[group]['controls'][4]])
    FCurves = []
    for fcu in act.fcurves:
        words = fcu.data_path.split('"')
        if (words[0] == "pose.bones[" and
                    words[1] in bones):
            FCurves.append(fcu)

    if FCurves == []:
        return

    for fcu in FCurves:
        act.fcurves.remove(fcu)

    # Put cleared bones back to rest pose
    bpy.ops.pose.loc_clear()
    bpy.ops.pose.rot_clear()
    bpy.ops.pose.scale_clear()

    # updateView3D()


def rotPoleToggle(rig, window='ALL', value=False, toggle=False, bake=False):

    scn = bpy.context.scene
    id_store = bpy.context.window_manager

    rig_id = rig.data['rig_id']
    leg_fk2ik = eval('bpy.ops.pose.rigify_leg_fk2ik_' + rig_id)
    arm_fk2ik = eval('bpy.ops.pose.rigify_arm_fk2ik_' + rig_id)
    leg_ik2fk = eval('bpy.ops.pose.rigify_leg_ik2fk_' + rig_id)
    arm_ik2fk = eval('bpy.ops.pose.rigify_arm_ik2fk_' + rig_id)
    limb_generated_names = get_limb_generated_names(rig)

    if window == 'ALL':
        frames = get_keyed_frames(rig)
        frames = [f for f in frames if f in range(id_store.rigify_transfer_start_frame, id_store.rigify_transfer_end_frame+1)]
    elif window == 'CURRENT':
        frames = [scn.frame_current]
    else:
        frames = [scn.frame_current]

    if not id_store.rigify_transfer_only_selected:
        bpy.ops.pose.select_all(action='DESELECT')
        pbones = rig.pose.bones
    else:
        pbones = bpy.context.selected_pose_bones
        bpy.ops.pose.select_all(action='DESELECT')

    for b in pbones:
        for group in limb_generated_names:
            names = limb_generated_names[group]

            if toggle:
                new_pole_vector_value = not rig.pose.bones[names['parent']]['pole_vector']
            else:
                new_pole_vector_value = value

            if b.name in names.values() or b.name in names['controls'] or b.name in names['ik_ctrl']:
                if names['limb_type'] == 'arm':
                    func1 = arm_fk2ik
                    func2 = arm_ik2fk
                    controls = names['controls']
                    ik_ctrl = names['ik_ctrl']
                    fk_ctrl = names['fk_ctrl']
                    parent = names['parent']
                    pole = names['pole']
                    rig.pose.bones[controls[0]].bone.select = not new_pole_vector_value
                    rig.pose.bones[controls[4]].bone.select = not new_pole_vector_value
                    rig.pose.bones[parent].bone.select = not new_pole_vector_value
                    rig.pose.bones[pole].bone.select = new_pole_vector_value

                    kwargs1 = {'uarm_fk': controls[1], 'farm_fk': controls[2], 'hand_fk': controls[3],
                              'uarm_ik': controls[0], 'farm_ik': ik_ctrl[1],
                              'hand_ik': controls[4]}
                    kwargs2 = {'uarm_fk': controls[1], 'farm_fk': controls[2], 'hand_fk': controls[3],
                              'uarm_ik': controls[0], 'farm_ik': ik_ctrl[1], 'hand_ik': controls[4],
                              'pole': pole, 'main_parent': parent}
                    args = (controls[0], controls[4], pole, parent)
                else:
                    func1 = leg_fk2ik
                    func2 = leg_ik2fk
                    controls = names['controls']
                    ik_ctrl = names['ik_ctrl']
                    fk_ctrl = names['fk_ctrl']
                    parent = names['parent']
                    pole = names['pole']
                    rig.pose.bones[controls[0]].bone.select = not new_pole_vector_value
                    rig.pose.bones[controls[6]].bone.select = not new_pole_vector_value
                    rig.pose.bones[controls[5]].bone.select = not new_pole_vector_value
                    rig.pose.bones[parent].bone.select = not new_pole_vector_value
                    rig.pose.bones[pole].bone.select = new_pole_vector_value

                    kwargs1 = {'thigh_fk': controls[1], 'shin_fk': controls[2], 'foot_fk': controls[3],
                              'mfoot_fk': controls[7], 'thigh_ik': controls[0], 'shin_ik': ik_ctrl[1],
                              'foot_ik': ik_ctrl[2], 'mfoot_ik': ik_ctrl[2]}
                    kwargs2 = {'thigh_fk': controls[1], 'shin_fk': controls[2], 'foot_fk': controls[3],
                              'mfoot_fk': controls[7], 'thigh_ik': controls[0], 'shin_ik': ik_ctrl[1],
                              'foot_ik': controls[6], 'pole': pole, 'footroll': controls[5], 'mfoot_ik': ik_ctrl[2],
                              'main_parent': parent}
                    args = (controls[0], controls[6], controls[5], pole, parent)

                for f in frames:
                    if bake and not bones_in_frame(f, rig, *args):
                        continue
                    scn.frame_set(f)
                    func1(**kwargs1)
                    rig.pose.bones[names['parent']]['pole_vector'] = new_pole_vector_value
                    func2(**kwargs2)
                    if bake:
                        bpy.ops.anim.keyframe_insert_menu(type='BUILTIN_KSI_VisualLocRot')
                        bpy.ops.anim.keyframe_insert_menu(type='Scaling')
                        overwrite_prop_animation(rig, rig.pose.bones[parent], 'pole_vector', new_pole_vector_value, [f])

                bpy.ops.pose.select_all(action='DESELECT')
                limb_generated_names.pop(group)
                break
    scn.frame_set(0)


class OBJECT_OT_IK2FK(bpy.types.Operator):
    """ Snaps IK limb on FK limb at current frame"""
    bl_idname = "rigify.ik2fk"
    bl_label = "IK2FK"
    bl_description = "Snaps IK limb on FK"
    bl_options = {'INTERNAL'}

    def execute(self,context):
        rig = context.object
        id_store = context.window_manager

        FktoIk(rig, window='CURRENT')

        return {'FINISHED'}


class OBJECT_OT_FK2IK(bpy.types.Operator):
    """ Snaps FK limb on IK limb at current frame"""
    bl_idname = "rigify.fk2ik"
    bl_label = "FK2IK"
    bl_description = "Snaps FK limb on IK"
    bl_options = {'INTERNAL'}

    def execute(self,context):
        rig = context.object

        IktoFk(rig, window='CURRENT')

        return {'FINISHED'}


class OBJECT_OT_TransferFKtoIK(bpy.types.Operator):
    """Transfers FK animation to IK"""
    bl_idname = "rigify.transfer_fk_to_ik"
    bl_label = "Transfer FK anim to IK"
    bl_description = "Transfer FK animation to IK bones"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        rig = context.object
        id_store = context.window_manager

        FktoIk(rig)

        return {'FINISHED'}


class OBJECT_OT_TransferIKtoFK(bpy.types.Operator):
    """Transfers FK animation to IK"""
    bl_idname = "rigify.transfer_ik_to_fk"
    bl_label = "Transfer IK anim to FK"
    bl_description = "Transfer IK animation to FK bones"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        rig = context.object

        IktoFk(rig)

        return {'FINISHED'}


class OBJECT_OT_ClearAnimation(bpy.types.Operator):
    bl_idname = "rigify.clear_animation"
    bl_label = "Clear Animation"
    bl_description = "Clear Animation For FK or IK Bones"
    bl_options = {'INTERNAL'}

    anim_type: StringProperty()

    def execute(self, context):
        rig = context.object
        scn = context.scene
        if not rig.animation_data:
            return {'FINISHED'}
        act = rig.animation_data.action
        if not act:
            return {'FINISHED'}

        clearAnimation(act, self.anim_type, names=get_limb_generated_names(rig))
        return {'FINISHED'}


class OBJECT_OT_Rot2Pole(bpy.types.Operator):
    bl_idname = "rigify.rotation_pole"
    bl_label = "Rotation - Pole toggle"
    bl_description = "Toggles IK chain between rotation and pole target"
    bl_options = {'INTERNAL'}

    bone_name: StringProperty(default='')
    window: StringProperty(default='ALL')
    toggle: BoolProperty(default=True)
    value: BoolProperty(default=True)
    bake: BoolProperty(default=True)

    def execute(self, context):
        rig = context.object

        if self.bone_name:
            bpy.ops.pose.select_all(action='DESELECT')
            rig.pose.bones[self.bone_name].bone.select = True

        rotPoleToggle(rig, window=self.window, toggle=self.toggle, value=self.value, bake=self.bake)
        return {'FINISHED'}


### Registering ###


classes = (
    DATA_OT_rigify_add_bone_groups,
    DATA_OT_rigify_use_standard_colors,
    DATA_OT_rigify_apply_selection_colors,
    DATA_OT_rigify_bone_group_add,
    DATA_OT_rigify_bone_group_add_theme,
    DATA_OT_rigify_bone_group_remove,
    DATA_OT_rigify_bone_group_remove_all,
    DATA_UL_rigify_bone_groups,
    DATA_MT_rigify_bone_groups_context_menu,
    DATA_PT_rigify_bone_groups,
    DATA_PT_rigify_layer_names,
    DATA_PT_rigify_buttons,
    BONE_PT_rigify_buttons,
    VIEW3D_PT_rigify_animation_tools,
    VIEW3D_PT_tools_rigify_dev,
    LayerInit,
    Generate,
    UpgradeMetarigTypes,
    SwitchToLegacy,
    Sample,
    EncodeMetarig,
    EncodeMetarigSample,
    EncodeWidget,
    OBJECT_OT_GetFrameRange,
    OBJECT_OT_FK2IK,
    OBJECT_OT_IK2FK,
    OBJECT_OT_TransferFKtoIK,
    OBJECT_OT_TransferIKtoFK,
    OBJECT_OT_ClearAnimation,
    OBJECT_OT_Rot2Pole,
)


def register():
    from bpy.utils import register_class

    # Classes.
    for cls in classes:
        register_class(cls)

    # Sub-modules.
    rot_mode.register()


def unregister():
    from bpy.utils import unregister_class

    # Sub-modules.
    rot_mode.unregister()

    # Classes.
    for cls in classes:
        unregister_class(cls)
