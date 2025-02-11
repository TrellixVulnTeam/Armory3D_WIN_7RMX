# ##### BEGIN GPL LICENSE BLOCK #####
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
# ##### END GPL LICENSE BLOCK #####


if "bpy" in locals():
    from importlib import reload

    asset_inspector = reload(asset_inspector)
    paths = reload(paths)
    utils = reload(utils)
    bg_blender = reload(bg_blender)
    autothumb = reload(autothumb)
    version_checker = reload(version_checker)
    search = reload(search)
    ui_panels = reload(ui_panels)
else:
    from blenderkit import asset_inspector, paths, utils, bg_blender, autothumb, version_checker, search, ui_panels

import tempfile, os, subprocess, json, re

import bpy
import requests

BLENDERKIT_EXPORT_DATA_FILE = "data.json"

from bpy.props import (  # TODO only keep the ones actually used when cleaning
    EnumProperty,
    BoolProperty,
)
from bpy.types import (
    Operator,
    Panel,
    AddonPreferences,
    PropertyGroup,
    UIList
)


def comma2array(text):
    commasep = text.split(',')
    ar = []
    for i, s in enumerate(commasep):
        s = s.strip()
        if s != '':
            ar.append(s)
    return ar


def get_app_version():
    ver = bpy.app.version
    return '%i.%i.%i' % (ver[0], ver[1], ver[2])


def add_version(data):
    app_version = get_app_version()
    addon_version = version_checker.get_addon_version()
    data["sourceAppName"] = "blender"
    data["sourceAppVersion"] = app_version
    data["addonVersion"] = addon_version


def params_to_dict(inputs, parameters=None):
    if parameters == None:
        parameters = []
    for k in inputs.keys():
        if type(inputs[k]) == list:
            strlist = ""
            for idx, s in enumerate(inputs[k]):
                strlist += s
                if idx < len(inputs[k]) - 1:
                    strlist += ','

            value = "%s" % strlist
        elif type(inputs[k]) != bool:
            value = inputs[k]
        else:
            value = str(inputs[k])
        parameters.append(
            {
                "parameterType": k,
                "value": value
            })
    return parameters


def write_to_report(props, text):
    props.report = props.report + text + '\n'


def get_missing_data_model(props):
    props.report = ''
    autothumb.update_upload_model_preview(None, None)

    if props.name == '':
        write_to_report(props, 'Set model name')
    if props.tags == '':
        write_to_report(props, 'Write at least 3 tags')
    if not props.has_thumbnail:
        write_to_report(props, 'Add thumbnail:')

        props.report += props.thumbnail_generating_state + '\n'
    if props.work_hours == 0.0:
        write_to_report(props, 'Fill in work hours')
    if props.engine == 'NONE':
        write_to_report(props, 'Set at least one rendering/output engine')
    if not any(props.dimensions):
        write_to_report(props, 'Run autotags operator or fill in dimensions manually')


def get_missing_data_scene(props):
    props.report = ''
    autothumb.update_upload_model_preview(None, None)

    if props.name == '':
        write_to_report(props, 'Set scene name')
    if props.tags == '':
        write_to_report(props, 'Write at least 3 tags')
    if not props.has_thumbnail:
        write_to_report(props, 'Add thumbnail:')

        props.report += props.thumbnail_generating_state + '\n'
    if props.work_hours == 0.0:
        write_to_report(props, 'Fill in work hours')
    if props.engine == 'NONE':
        write_to_report(props, 'Set at least one rendering/output engine')


def get_missing_data_material(props):
    props.report = ''
    autothumb.update_upload_material_preview(None, None)
    if props.name == '':
        write_to_report(props, 'Set material name')
    if props.tags == '':
        write_to_report(props, 'Write at least 3 tags')
    if not props.has_thumbnail:
        write_to_report(props, 'Add thumbnail:')
        props.report += props.thumbnail_generating_state
    if props.engine == 'NONE':
        write_to_report(props, 'Set rendering/output engine')


def get_missing_data_brush(props):
    autothumb.update_upload_brush_preview(None, None)
    props.report = ''
    if props.name == '':
        write_to_report(props, 'Set brush name')
    if props.tags == '':
        write_to_report(props, 'Write at least 3 tags')
    if not props.has_thumbnail:
        write_to_report(props, 'Add thumbnail:')
        props.report += props.thumbnail_generating_state


def sub_to_camel(content):
    replaced = re.sub(r"_.",
                      lambda m: m.group(0)[1].upper(), content)
    return (replaced)


def camel_to_sub(content):
    replaced = re.sub(r"[A-Z]", lambda m: '_' + m.group(0).lower(), content)
    return replaced


def get_upload_data(self, context, asset_type):
    user_preferences = bpy.context.preferences.addons['blenderkit'].preferences
    api_key = user_preferences.api_key

    export_data = {
        "type": asset_type,
    }
    upload_params = {}
    if asset_type == 'MODEL':
        # Prepare to save the file
        mainmodel = utils.get_active_model()

        props = mainmodel.blenderkit

        obs = utils.get_hierarchy(mainmodel)
        obnames = []
        for ob in obs:
            obnames.append(ob.name)
        export_data["models"] = obnames
        export_data["thumbnail_path"] = bpy.path.abspath(props.thumbnail)

        eval_path_computing = "bpy.data.objects['%s'].blenderkit.uploading" % mainmodel.name
        eval_path_state = "bpy.data.objects['%s'].blenderkit.upload_state" % mainmodel.name
        eval_path = "bpy.data.objects['%s']" % mainmodel.name

        engines = [props.engine.lower()]
        if props.engine1 != 'NONE':
            engines.append(props.engine1.lower())
        if props.engine2 != 'NONE':
            engines.append(props.engine2.lower())
        if props.engine3 != 'NONE':
            engines.append(props.engine3.lower())
        if props.engine == 'OTHER':
            engines.append(props.engine_other.lower())

        style = props.style.lower()
        if style == 'OTHER':
            style = props.style_other.lower()

        pl_dict = {'FINISHED': 'finished', 'TEMPLATE': 'template'}

        upload_data = {
            "assetType": 'model',

        }
        upload_params = {
            "productionLevel": props.production_level.lower(),
            "model_style": style,
            "engines": engines,
            "modifiers": comma2array(props.modifiers),
            "materials": comma2array(props.materials),
            "shaders": comma2array(props.shaders),
            "uv": props.uv,
            "dimensionX": round(props.dimensions[0], 4),
            "dimensionY": round(props.dimensions[1], 4),
            "dimensionZ": round(props.dimensions[2], 4),

            "boundBoxMinX": round(props.bbox_min[0], 4),
            "boundBoxMinY": round(props.bbox_min[1], 4),
            "boundBoxMinZ": round(props.bbox_min[2], 4),

            "boundBoxMaxX": round(props.bbox_max[0], 4),
            "boundBoxMaxY": round(props.bbox_max[1], 4),
            "boundBoxMaxZ": round(props.bbox_max[2], 4),

            "animated": props.animated,
            "rig": props.rig,
            "simulation": props.simulation,
            "purePbr": props.pbr,
            "faceCount": props.face_count,
            "faceCountRender": props.face_count_render,
            "manifold": props.manifold,
            "objectCount": props.object_count,

            # "scene": props.is_scene,
        }
        if props.use_design_year:
            upload_params["designYear"] = props.design_year
        if props.condition != 'UNSPECIFIED':
            upload_params["condition"] = props.condition.lower()
        if props.pbr:
            pt = props.pbr_type
            pt = pt.lower()
            upload_params["pbrType"] = pt

        if props.texture_resolution_max > 0:
            upload_params["textureResolutionMax"] = props.texture_resolution_max
            upload_params["textureResolutionMin"] = props.texture_resolution_min
        if props.mesh_poly_type != 'OTHER':
            upload_params["meshPolyType"] = props.mesh_poly_type.lower()  # .replace('_',' ')

        optional_params = ['manufacturer', 'designer', 'design_collection', 'design_variant']
        for p in optional_params:
            if eval('props.%s' % p) != '':
                upload_params[sub_to_camel(p)] = eval('props.%s' % p)

    if asset_type == 'SCENE':
        # Prepare to save the file
        s = bpy.context.scene

        props = s.blenderkit

        export_data["scene"] = s.name
        export_data["thumbnail_path"] = bpy.path.abspath(props.thumbnail)

        eval_path_computing = "bpy.data.scenes['%s'].blenderkit.uploading" % s.name
        eval_path_state = "bpy.data.scenes['%s'].blenderkit.upload_state" % s.name
        eval_path = "bpy.data.scenes['%s']" % s.name

        engines = [props.engine.lower()]
        if props.engine1 != 'NONE':
            engines.append(props.engine1.lower())
        if props.engine2 != 'NONE':
            engines.append(props.engine2.lower())
        if props.engine3 != 'NONE':
            engines.append(props.engine3.lower())
        if props.engine == 'OTHER':
            engines.append(props.engine_other.lower())

        style = props.style.lower()
        if style == 'OTHER':
            style = props.style_other.lower()

        pl_dict = {'FINISHED': 'finished', 'TEMPLATE': 'template'}

        upload_data = {
            "assetType": 'scene',

        }
        upload_params = {
            "productionLevel": props.production_level.lower(),
            "model_style": style,
            "engines": engines,
            "modifiers": comma2array(props.modifiers),
            "materials": comma2array(props.materials),
            "shaders": comma2array(props.shaders),
            "uv": props.uv,

            "animated": props.animated,
            # "simulation": props.simulation,
            "purePbr": props.pbr,
            "faceCount": 1,  # props.face_count,
            "faceCountRender": 1,  # props.face_count_render,
            "objectCount": 1,  # props.object_count,

            # "scene": props.is_scene,
        }
        if props.use_design_year:
            upload_params["designYear"] = props.design_year
        if props.condition != 'UNSPECIFIED':
            upload_params["condition"] = props.condition.lower()
        if props.pbr:
            pt = props.pbr_type
            pt = pt.lower()
            upload_params["pbrType"] = pt

        if props.texture_resolution_max > 0:
            upload_params["textureResolutionMax"] = props.texture_resolution_max
            upload_params["textureResolutionMin"] = props.texture_resolution_min
        if props.mesh_poly_type != 'OTHER':
            upload_params["meshPolyType"] = props.mesh_poly_type.lower()  # .replace('_',' ')

    elif asset_type == 'MATERIAL':
        mat = bpy.context.active_object.active_material
        props = mat.blenderkit

        # props.name = mat.name

        export_data["material"] = str(mat.name)
        export_data["thumbnail_path"] = bpy.path.abspath(props.thumbnail)
        # mat analytics happen here, since they don't take up any time...
        asset_inspector.check_material(props, mat)

        eval_path_computing = "bpy.data.materials['%s'].blenderkit.uploading" % mat.name
        eval_path_state = "bpy.data.materials['%s'].blenderkit.upload_state" % mat.name
        eval_path = "bpy.data.materials['%s']" % mat.name

        engine = props.engine
        if engine == 'OTHER':
            engine = props.engine_other
        engine = engine.lower()
        style = props.style.lower()
        if style == 'OTHER':
            style = props.style_other.lower()

        upload_data = {
            "assetType": 'material',

        }

        upload_params = {
            "material_style": style,
            "engine": engine,
            "shaders": comma2array(props.shaders),
            "uv": props.uv,
            "animated": props.animated,
            "purePbr": props.pbr,
            "textureSizeMeters": props.texture_size_meters,

        }

        if props.pbr:
            upload_params["pbrType"] = props.pbr_type.lower()

        if props.texture_resolution_max > 0:
            upload_params["textureResolutionMax"] = props.texture_resolution_max
            upload_params["textureResolutionMin"] = props.texture_resolution_min

    elif asset_type == 'BRUSH':
        brush = utils.get_active_brush()

        props = brush.blenderkit
        # props.name = brush.name

        export_data["brush"] = str(brush.name)
        export_data["thumbnail_path"] = bpy.path.abspath(brush.icon_filepath)

        eval_path_computing = "bpy.data.brushes['%s'].blenderkit.uploading" % brush.name
        eval_path_state = "bpy.data.brushes['%s'].blenderkit.upload_state" % brush.name
        eval_path = "bpy.data.brushes['%s']" % brush.name

        # mat analytics happen here, since they don't take up any time...

        brush_type = ''
        if bpy.context.sculpt_object is not None:
            brush_type = 'sculpt'

        elif bpy.context.image_paint_object:  # could be just else, but for future p
            brush_type = 'texture_paint'

        upload_params = {
            "mode": brush_type,
        }

        upload_data = {
            "assetType": 'brush',
        }

    elif asset_type == 'TEXTURE':
        style = props.style
        if style == 'OTHER':
            style = props.style_other

        upload_data = {
            "assetType": 'texture',

        }
        upload_params = {
            "style": style,
            "animated": props.animated,
            "purePbr": props.pbr,
            "resolution": props.resolution,
        }
        if props.pbr:
            pt = props.pbr_type
            pt = pt.lower()
            upload_data["pbrType"] = pt

    add_version(upload_data)

    upload_data["name"] = props.name
    upload_data["description"] = props.description
    upload_data["tags"] = comma2array(props.tags)
    if props.category == '':
        upload_data["category"] = asset_type.lower()
    else:
        upload_data["category"] = props.category
    if props.subcategory != '':
        upload_data["category"] = props.subcategory
    upload_data["license"] = props.license
    upload_data["isFree"] = props.is_free
    upload_data["isPrivate"] = props.is_private == 'PRIVATE'
    upload_data["token"] = user_preferences.api_key

    if props.asset_base_id != '':
        upload_data['assetBaseId'] = props.asset_base_id
        upload_data['id'] = props.id

    upload_data['parameters'] = upload_params

    return export_data, upload_data, eval_path_computing, eval_path_state, eval_path, props


def mark_for_validation(self, context, asset_type):
    props = utils.get_upload_props()
    props.upload_state = 'marking for validation'
    user_preferences = bpy.context.preferences.addons['blenderkit'].preferences

    upload_data = {
        "verificationStatus": "ready"
    }

    url = paths.get_api_url() + 'assets/'

    headers = utils.get_headers(user_preferences.api_key)

    url += props.id + '/'

    try:
        r = requests.patch(url, json=upload_data, headers=headers, verify=True)  # files = files,
        props.upload_state = 'marked for validation'
    except requests.exceptions.RequestException as e:
        props.upload_state = str(e)
        props.uploading = False
        return {'CANCELLED'}
    return {'FINISHED'}


def get_upload_location(props):
    scene = bpy.context.scene
    ui_props = scene.blenderkitUI
    if ui_props.asset_type == 'MODEL':
        if bpy.context.active_object is not None:
            ob = utils.get_active_model()
            return ob.location
    if ui_props.asset_type == 'SCENE':
        return None
    elif ui_props.asset_type == 'MATERIAL':
        if bpy.context.active_object is not None and bpy.context.active_object.active_material is not None:
            return bpy.context.active_object.location
    elif ui_props.asset_type == 'TEXTURE':
        return None
    elif ui_props.asset_type == 'BRUSH':
        return None
    return None


def check_storage_quota(props):
    if props.is_private == 'PUBLIC':
        return True

    profile = bpy.context.window_manager.get('bkit profile')
    if profile is None or profile.get('remainingPrivateQuota') is None:
        preferences = bpy.context.preferences.addons['blenderkit'].preferences
        adata = search.request_profile(preferences.api_key)
        if adata is None:
            props.report = 'User profile not retrieved.'
            return False
        search.write_profile(adata)
        profile = adata
    quota = profile['user'].get('remainingPrivateQuota')
    if quota is None or quota > 0:
        return True
    props.report = 'Private storage quota exceeded.'
    return False


def start_upload(self, context, asset_type, as_new, metadata_only):
    props = utils.get_upload_props()
    storage_quota_ok = check_storage_quota(props)
    if not storage_quota_ok:
        self.report({'ERROR_INVALID_INPUT'}, props.report)
        return {'CANCELLED'}

    location = get_upload_location(props)
    props.upload_state = 'preparing upload'
    # do this for fixing long tags in some upload cases
    props.tags = props.tags[:]

    props.name = props.name.strip()
    # TODO  move this to separate function
    # check for missing metadata
    if asset_type == 'MODEL':
        get_missing_data_model(props)
    if asset_type == 'SCENE':
        get_missing_data_scene(props)
    elif asset_type == 'MATERIAL':
        get_missing_data_material(props)
    elif asset_type == 'BRUSH':
        get_missing_data_brush(props)

    if props.report != '':
        self.report({'ERROR_INVALID_INPUT'}, props.report)
        return {'CANCELLED'}

    if as_new:
        props.asset_base_id = ''
        props.id = ''
    export_data, upload_data, eval_path_computing, eval_path_state, eval_path, props = get_upload_data(self, context,
                                                                                                       asset_type)
    # utils.pprint(upload_data)
    upload_data['parameters'] = params_to_dict(
        upload_data['parameters'])  # weird array conversion only for upload, not for tooltips.

    binary_path = bpy.app.binary_path
    script_path = os.path.dirname(os.path.realpath(__file__))
    basename, ext = os.path.splitext(bpy.data.filepath)
    # if not basename:
    #     basename = os.path.join(basename, "temp")
    if not ext:
        ext = ".blend"
    tempdir = tempfile.mkdtemp()
    source_filepath = os.path.join(tempdir, "export_blenderkit" + ext)
    clean_file_path = paths.get_clean_filepath()
    data = {
        'clean_file_path': clean_file_path,
        'source_filepath': source_filepath,
        'temp_dir': tempdir,
        'export_data': export_data,
        'upload_data': upload_data,
        'debug_value': bpy.app.debug_value,
    }
    datafile = os.path.join(tempdir, BLENDERKIT_EXPORT_DATA_FILE)

    # check if thumbnail exists:

    if not os.path.exists(export_data["thumbnail_path"]):
        props.upload_state = 'Thumbnail not found'
        props.uploading = False
        return {'CANCELLED'}

    # first upload metadata to server, so it can be saved inside the current file
    url = paths.get_api_url() + 'assets/'

    headers = utils.get_headers(upload_data['token'])

    # upload_data['license'] = 'ovejajojo'
    json_metadata = upload_data  # json.dumps(upload_data, ensure_ascii=False).encode('utf8')
    global reports
    if props.asset_base_id == '':
        try:
            r = requests.post(url, json=json_metadata, headers=headers, verify=True)  # files = files,
            props.upload_state = 'uploaded metadata'
            utils.p(r.text)
        except requests.exceptions.RequestException as e:
            print(e)
            props.upload_state = str(e)
            props.uploading = False
            return {'CANCELLED'}

    else:
        url += props.id + '/'
        try:
            if not metadata_only:
                json_metadata["verificationStatus"] = "uploading"
            r = requests.put(url, json=json_metadata, headers=headers, verify=True)  # files = files,
            props.upload_state = 'uploaded metadata'
            # parse the reqest
            # print('uploaded metadata')
            # print(r.text)
        except requests.exceptions.RequestException as e:
            print(e)
            props.upload_state = str(e)
            props.uploading = False
            return {'CANCELLED'}

    # props.upload_state = 'step 1'
    if metadata_only:
        props.uploading = False

        return {'FINISHED'}
    try:
        rj = r.json()
        if props.asset_base_id == '':
            props.asset_base_id = rj['assetBaseId']
            props.id = rj['id']

        upload_data['assetBaseId'] = props.asset_base_id
        upload_data['id'] = props.id

        bpy.ops.wm.save_mainfile()
        # fa
        props.uploading = True
        # save a copy of actual scene but don't interfere with the users models
        bpy.ops.wm.save_as_mainfile(filepath=source_filepath, compress=False, copy=True)

        with open(datafile, 'w') as s:
            json.dump(data, s)

        proc = subprocess.Popen([
            binary_path,
            "--background",
            "-noaudio",
            clean_file_path,
            "--python", os.path.join(script_path, "upload_bg.py"),
            "--", datafile  # ,filepath, tempdir
        ], bufsize=5000, stdout=subprocess.PIPE, stdin=subprocess.PIPE)

        bg_blender.add_bg_process(eval_path_computing=eval_path_computing, eval_path_state=eval_path_state,
                                  eval_path=eval_path, process_type='UPLOAD', process=proc, location=location)

    except Exception as e:
        props.upload_state = str(e)
        props.uploading = False
        return {'CANCELLED'}

    return {'FINISHED'}


asset_types = (
    ('MODEL', 'Model', 'set of objects'),
    ('SCENE', 'Scene', 'scene'),
    ('MATERIAL', 'Material', 'any .blend Material'),
    ('TEXTURE', 'Texture', 'a texture, or texture set'),
    ('BRUSH', 'Brush', 'brush, can be any type of blender brush'),
    ('ADDON', 'Addon', 'addnon'),
)


class ModelUploadOperator(Operator):
    """Tooltip"""
    bl_idname = "object.blenderkit_upload"
    bl_description = "Upload or re-upload asset + thumbnail + metadata"

    bl_label = "BlenderKit asset upload"

    # type of upload - model, material, textures, e.t.c.
    asset_type: EnumProperty(
        name="Type",
        items=asset_types,
        description="Type of upload",
        default="MODEL",
    )

    as_new: BoolProperty(
        name="upload as new",
        description="delets asset id and uploads as new file",
        default=False,
        options={'SKIP_SAVE'}
    )

    metadata_only: BoolProperty(
        name="upload metadata",
        description="update only metadata",
        default=False,
        options={'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context):
        return bpy.context.active_object is not None

    def execute(self, context):
        bpy.ops.object.blenderkit_auto_tags()
        props = utils.get_upload_props()

        # in case of name change, we have to reupload everything, since the name is stored in blender file,
        # and is used for linking to scene
        metadata_only = self.metadata_only
        if props.name_changed:
            # print('has to reupload whole data, name has changed.')
            self.metadata_only = False
            props.name_changed = False

        result = start_upload(self, context, self.asset_type, self.as_new, self.metadata_only)

        return result

    def draw(self, context):
        props = utils.get_upload_props()
        layout = self.layout

        if self.as_new:
            layout.label(text="Really upload as new? ")
            layout.label(text="Do this only when you create a new asset from an old one.")
            layout.label(text="For updates of thumbnail or model use reupload.")

        if props.is_private == 'PUBLIC':
            ui_panels.label_multiline(layout, text='Since this version (1.0.24), '
                                                   'PUBLIC ASSETS ARE VALIDATED AUTOMATICALLY '
                                                   ' after upload. '
                                                   'Click Ok to proceed.')

    def invoke(self, context, event):
        props = utils.get_upload_props()

        if self.as_new or props.is_private == 'PUBLIC':
            return context.window_manager.invoke_props_dialog(self)
        else:
            return self.execute(context)


class ModelMarkForValidation(Operator):
    """Tooltip"""
    bl_idname = "object.blenderkit_mark_for_validation"
    bl_description = "After this, model can be validated by our validators and \n then be part of the public database"

    bl_label = "Mark for validation"

    # type of upload - model, material, textures, e.t.c.
    asset_type: EnumProperty(
        name="type",
        items=asset_types,
        description="Type of upload",
        default="MODEL",
    )

    @classmethod
    def poll(cls, context):
        props = utils.get_upload_props()
        return bpy.context.active_object is not None and props.asset_base_id != ''

    def execute(self, context):
        result = mark_for_validation(self, context, self.asset_type)

        return result


# TODO this is for upldating by creators, if they edit metadata on server or want to upload from older file version.
# class GetMetadataFromServer(Operator):
#     """Tooltip"""
#     bl_idname = "object.blenderkit_get_from_server"
#     bl_description ="After this, model can be validated by our validators and \n then be part of the public database"
#
#     bl_label = "Mark for validation"
#
#     # type of upload - model, material, textures, e.t.c.
#     asset_type : EnumProperty(
#         name="type",
#         items=asset_types,
#         description="Type of upload",
#         default="MODEL",
#     )
#
#     @classmethod
#     def poll(cls, context):
#         props = utils.get_upload_props()
#         return bpy.context.active_object is not None and props.asset_base_id != ''
#
#     def execute(self, context):
#         result = mark_for_validation(self, context, self.asset_type)
#
#         return result


def register_upload():
    bpy.utils.register_class(ModelUploadOperator)
    bpy.utils.register_class(ModelMarkForValidation)


def unregister_upload():
    bpy.utils.unregister_class(ModelUploadOperator)
    bpy.utils.unregister_class(ModelMarkForValidation)
