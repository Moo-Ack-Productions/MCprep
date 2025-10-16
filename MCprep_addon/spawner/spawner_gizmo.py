from dataclasses import dataclass
from typing import Optional
import bpy
from bpy_extras import view3d_utils
import gpu
from gpu_extras.batch import batch_for_shader
import math
from mathutils import Matrix, Quaternion, Vector
from mathutils.geometry import intersect_line_plane

ZERO_VECTOR = Vector((0, 0, 0))
UP_VECTOR = Vector((0, 0, 1))


@dataclass
class HitVector:
    location: Vector
    normal: Vector
    rotation: Quaternion


def draw_fading_grid(shader_info, size, subdivisions, rings, base_color):
    """Creates a grid with a fading circle gradient"""
    half_size = size / 2.0
    step = size / subdivisions

    # Pre-calculate all possible small line segments for the grid
    all_segments = []
    for i in range(subdivisions + 1):
        # Horizontal segments
        for j in range(subdivisions):
            x1 = -half_size + j * step
            y = -half_size + i * step
            all_segments.append(((x1, y, 0.0), (x1 + step, y, 0.0)))
        # Vertical segments
        for j in range(subdivisions):
            x = -half_size + i * step
            y1 = -half_size + j * step
            all_segments.append(((x, y1, 0.0), (x, y1 + step, 0.0)))

    # Draw the segments in rings with different alpha values
    for r in range(rings):
        alpha = ((1.0 - (r / rings)) ** 1.5) * 0.8
        color = (*base_color, alpha)

        inner_radius = (r / rings) * half_size
        outer_radius = ((r + 1) / rings) * half_size

        coords = []
        for p1, p2 in all_segments:
            # Check if the midpoint of the segment is in the current ring
            mid_x = (p1[0] + p2[0]) / 2
            mid_y = (p1[1] + p2[1]) / 2
            dist = math.sqrt(mid_x**2 + mid_y**2)

            if dist >= inner_radius and dist < outer_radius:
                coords.extend([p1, p2])

        if not coords:
            continue

        batch = batch_for_shader(shader_info, "LINES", {"pos": coords})
        shader_info.bind()
        shader_info.uniform_float("color", color)
        batch.draw(shader_info)


def draw_callback(hit_vector: HitVector) -> None:
    """Callback function to call when drawing the gizmo"""
    shader_info = gpu.shader.from_builtin("UNIFORM_COLOR")

    original_blend = gpu.state.blend_get()
    original_depth_test = gpu.state.depth_test_get()
    gpu.state.blend_set("ALPHA")
    gpu.state.depth_test_set("NONE")

    transform_matrix = (
        Matrix.Translation(hit_vector.location)
        @ hit_vector.rotation.to_matrix().to_4x4()
    )

    gpu.matrix.push()
    gpu.matrix.multiply_matrix(transform_matrix)

    draw_fading_grid(
        shader_info, size=2.0, subdivisions=20, rings=10, base_color=(0.7, 0.7, 0.7)
    )

    gpu.matrix.pop()
    gpu.state.blend_set(original_blend)
    gpu.state.depth_test_set(original_depth_test)


def update_raycast(context, event) -> Optional[HitVector]:
    """Given the context of the scene, update the location, normal, and rotation of the ray"""
    mouse_pos = (event.mouse_region_x, event.mouse_region_y)
    region, region_3d = context.region, context.space_data.region_3d
    ray_origin = view3d_utils.region_2d_to_origin_3d(region, region_3d, mouse_pos)
    ray_direction = view3d_utils.region_2d_to_vector_3d(region, region_3d, mouse_pos)
    depsgraph = context.evaluated_depsgraph_get()
    result, location, normal, _, _, _ = context.scene.ray_cast(
        depsgraph, ray_origin, ray_direction
    )

    if result:
        return HitVector(location, normal, UP_VECTOR.rotation_difference(normal))
    else:
        intersection = intersect_line_plane(
            ray_origin, ray_origin + ray_direction, ZERO_VECTOR, UP_VECTOR
        )
        if intersection:
            return HitVector(intersection, UP_VECTOR, Quaternion())
    # If there is no hit, then don't return a HitVector
    return None
