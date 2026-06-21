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

from typing import Callable
import bpy
from pathlib import Path

from .conf import env, MCprepError
from .exporter_glue.interfaces import EXPORTER_INTERFACES
from .commonmcobj_parser import CommonMCOBJ, CommonMCOBJTextureType
from . import tracking
from . import util
from .world_tools import WorldImporterBase

StepArgs = float | Path | tuple[int, int, int] | tuple[float, float, float] | CommonMCOBJTextureType

class MCPREP_OT_reload_world_single(bpy.types.Operator, WorldImporterBase):
    bl_idname = "mcprep.reload_world_single"
    bl_label = "Reload Single Chunk"
    bl_description = "Reload a single chunk"

    skipUsage: bpy.props.BoolProperty(
        default=False,
        options={'HIDDEN'})

    track_function = "reload_world_single"

    _timer = None
    proc = None
    original_import = None
    path_obj = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            if self.proc.poll() is None:
                return {'PASS_THROUGH'}

            # Process finished
            context.window_manager.event_timer_remove(self._timer)
            env.global_lock = False # Release global lock

            if self.proc.returncode != 0:
                self.report({'ERROR'}, f"Export failed with return code {self.proc.returncode}")
                return {'CANCELLED'}

            if not self.original_import:
                self.report({'ERROR'}, "Original object not found!")
                return {'CANCELLED'}

            if not self.path_obj:
                self.report({'ERROR'}, "Path to OBJ not found!")
                return {'CANCELLED'}

            # TODO: Figure out an operatorless way of doing this
            with context.temp_override(selected_objects=[self.original_import], active_object=self.original_import):
                bpy.ops.object.delete()

            # Since all of the world importer code
            # has been abstracted to a simple base
            # class, we can make this operator another
            # world importer
            path_res = self.validate_and_return_header(self.path_obj)
            if isinstance(path_res, MCprepError):
                self.report({"ERROR"}, path_res.msg)
                return {'CANCELLED'}

            path, header = path_res
            if not isinstance(header, CommonMCOBJ):
                self.report({"ERROR"}, "OBJ doesn't use the CommonMCOBJ spec, CommonMCOBJ is required!")
                return {'CANCELLED'}

            res = self.import_obj_file(context,
                                 path,
                                 header,
                                 None,
                                 mineways_fix_smooth_shading_artifacts=False)

            if isinstance(res, MCprepError):
                self.report({"ERROR"}, res.msg)
                return {'CANCELLED'}
            elif res is not None: # warnings
                for ret in res:
                    self.report({"INFO"}, ret.msg)

            return {'FINISHED'}

        return {'PASS_THROUGH'}

    @tracking.report_error
    def execute(self, context):
        if env.global_lock:
            self.report({'ERROR'}, "Another process is already running!")
            return {'CANCELLED'}

        obj = context.active_object

        # We're only going to support CommonMCOBJ
        # exports with the world bridge
        if "COMMONMCOBJ_HEADER" not in obj or obj["PARENTED_EMPTY"] is None:
            self.report({'ERROR'}, "Reloading only supports worlds with CommonMCOBJ metadata!")
            return {'CANCELLED'}
        elif "MCPREP_OBJ_FILE_PATH" not in obj:
            self.report({'ERROR'}, "Selected chunk was imported with an old version of MCprep, reloading not supported!")
            return {'CANCELLED'}


        header = util.return_commonmcobj_header(obj)
        if header.exporter not in EXPORTER_INTERFACES:
            self.report({'ERROR'}, f"No exporter interface for {header.exporter}!")
            return {'CANCELLED'}

        match header.exporter:
            case "jmc2obj":
                addon_prefs = util.get_user_preferences(context)
                executable = Path(addon_prefs.open_jmc2obj_path)
            case _:
                self.report({'ERROR'}, "Cannot get executable!")
                return {'CANCELLED'}

        self.path_obj = Path(obj["MCPREP_OBJ_FILE_PATH"])
        self.original_import = obj

        builder = EXPORTER_INTERFACES[header.exporter](executable, self.path_obj, env.resource_packs)
        steps: tuple[tuple[Callable[..., None | MCprepError], tuple[StepArgs, ...]], ...] = (
            (builder.set_world_path, (Path(header.world_path),)),
            (builder.set_export_bounds, (header.export_bounds_min, header.export_bounds_max)),
            (builder.set_export_offset, (header.export_offset,)),
            (builder.set_block_scale, (header.block_scale,)),
            (builder.set_texture_type, (header.texture_type,)),
            (builder.set_split_blocks, (header.has_split_blocks,)),
            (builder.prep_for_export, ()),
        )

        for step, args in steps:
            res = step(*args)
            if isinstance(res, MCprepError):
                self.report({'ERROR'}, res.msg)
                return {'CANCELLED'}

        env.global_lock = True
        if builder.interpreter is None:
            res = util.run_executable(builder.executable_path, builder.args, asynchronous=True)
        else:
            command = str(builder.interpreter.interpreter_exec)
            args = builder.interpreter.interpreter_args + [str(builder.executable_path)] + builder.args
            res = util.run_executable(command, args, asynchronous=True)

        if isinstance(res, MCprepError):
            env.global_lock = False
            self.report({'ERROR'}, res.msg)
            return {'CANCELLED'}

        self.proc = res

        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

classes = (MCPREP_OT_reload_world_single,)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
