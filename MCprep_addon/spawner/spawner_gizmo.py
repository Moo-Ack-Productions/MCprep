import bpy
import gpu
from gpu_extras.batch import batch_for_shader
import math

def draw_fading_grid(shader_info, size, subdivisions, rings, base_color):
    """
    Draws a grid with a circular falloff by drawing small segments
    in concentric rings based on their distance from the center.
    """
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

        batch = batch_for_shader(shader_info, 'LINES', {"pos": coords})
        shader_info.bind()
        shader_info.uniform_float("color", color)
        batch.draw(shader_info)
