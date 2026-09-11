from __future__ import annotations

from collections import Counter, deque
from typing import Any, cast

import bpy


def _is_layoutable(node: bpy.types.Node) -> bool:
    """Check if a node should be included in column-based layout.

    Frame nodes are containers and reroute nodes are tiny routing helpers;
    neither should occupy a full column slot.
    """
    return node.bl_idname not in ("NodeFrame", "NodeReroute")


def build_dependency_graph(
    tree: bpy.types.NodeTree,
) -> tuple[dict[bpy.types.Node, set[bpy.types.Node]], Counter]:
    """Build a graph of node dependencies and count input connections.

    Only layoutable nodes (excluding frames and reroutes) are included.
    """
    layoutable = {n for n in tree.nodes if _is_layoutable(n)}
    dependency_graph: dict[bpy.types.Node, set[bpy.types.Node]] = {
        node: set() for node in layoutable
    }
    socket_input_connection_count: Counter = Counter()

    for link in tree.links:
        if link.from_node in layoutable and link.to_node in layoutable:
            dependency_graph[link.from_node].add(link.to_node)
        socket_input_connection_count[link.to_socket] += 1

    return dependency_graph, socket_input_connection_count


def topological_sort(
    dependency_graph: dict[bpy.types.Node, set[bpy.types.Node]],
) -> list[bpy.types.Node]:
    """Sort nodes in topological (dependency) order using Kahn's algorithm."""
    incoming = {node: 0 for node in dependency_graph}
    for dependents in dependency_graph.values():
        for target in dependents:
            incoming[target] += 1

    queue = deque(node for node, count in incoming.items() if count == 0)
    result: list[bpy.types.Node] = []

    while queue:
        current = queue.popleft()
        result.append(current)
        for dependent in dependency_graph[current]:
            incoming[dependent] -= 1
            if incoming[dependent] == 0:
                queue.append(dependent)

    return result


def organize_into_columns(
    nodes_in_order: list[bpy.types.Node],
    dependency_graph: dict[bpy.types.Node, set[bpy.types.Node]],
) -> list[list[bpy.types.Node]]:
    """Assign each node to a column based on its furthest dependent."""
    columns: list[list[bpy.types.Node]] = []
    column_of: dict[bpy.types.Node, int] = {}

    for node in reversed(nodes_in_order):
        col = (
            max(
                (column_of[dep] for dep in dependency_graph[node]),
                default=-1,
            )
            + 1
        )
        column_of[node] = col

        if col == len(columns):
            columns.append([node])
        else:
            columns[col].append(node)

    # reverse so flow goes left-to-right
    return list(reversed(columns))


def calculate_node_dimensions(
    node: bpy.types.Node,
    socket_input_connection_count: Counter,
    interface_scale: float,
) -> tuple[float, float]:
    """Calculate the visual dimensions of a node.

    When a node is collapsed (``node.hide is True``) only linked sockets
    contribute to the height, and header / property / vector-expansion rows
    are omitted.
    """
    HEADER = 20
    SOCKET = 32
    HIDDEN_SOCKET = 14
    HIDDEN_HEADER = 30

    if node.hide:
        linked_inputs = sum(1 for s in node.inputs if s.enabled and s.is_linked)
        linked_outputs = sum(1 for s in node.outputs if s.enabled and s.is_linked)
        visible = max(linked_inputs, linked_outputs, 1)
        height = (HIDDEN_HEADER + visible * HIDDEN_SOCKET) * interface_scale
        return node.width, height
    PROPERTY_ROW = 28
    VECTOR_EXPANDED = 84

    enabled_inputs = sum(1 for s in node.inputs if s.enabled)
    enabled_outputs = sum(1 for s in node.outputs if s.enabled)

    # count properties specific to this node type (not inherited)
    # ``bl_rna`` exists on bpy classes via their metaclass, invisible to type
    # checkers looking at plain ``type``.
    inherited_ids = {
        prop.identifier
        for base in type(node).__bases__
        for prop in cast(Any, base).bl_rna.properties
    }
    node_property_count = sum(
        1 for prop in node.bl_rna.properties if prop.identifier not in inherited_ids
    )

    # count vector inputs that need expanded UI widgets (not connected)
    unconnected_vectors = sum(
        1
        for s in node.inputs
        if s.enabled and s.type == "VECTOR" and socket_input_connection_count[s] == 0
    )

    height = (
        HEADER
        + enabled_outputs * SOCKET
        + node_property_count * PROPERTY_ROW
        + enabled_inputs * SOCKET
        + unconnected_vectors * VECTOR_EXPANDED
    ) * interface_scale

    return node.width, height


def _socket_index(socket: bpy.types.NodeSocket) -> int:
    """Return the index of a socket among its node's enabled sockets."""
    assert socket.node is not None
    collection = socket.node.inputs if not socket.is_output else socket.node.outputs
    idx = 0
    for s in collection:
        if s == socket:
            return idx
        if s.enabled:
            idx += 1
    return idx


def _reduce_crossings(
    columns: list[list[bpy.types.Node]],
    tree: bpy.types.NodeTree,
    passes: int = 4,
) -> None:
    """Reorder nodes within columns to reduce edge crossings.

    Uses the barycenter heuristic with socket-level precision: for each node
    compute its weight from the position of the sockets it connects to in the
    adjacent column, then sort by that weight.  This correctly distinguishes
    nodes that connect to different sockets on the same target.

    Alternating forward and backward sweeps iteratively improve the ordering.
    """
    if len(columns) < 2:
        return

    layoutable = {n for col in columns for n in col}
    col_of = {n: ci for ci, col in enumerate(columns) for n in col}

    # Pre-compute per-node link weights towards each adjacent column direction.
    # For a forward sweep (fixing col i, sorting col i+1), a node in col i+1
    # cares about its connections INTO col i.  The weight of each connection is
    # the position of the *node* in the fixed column plus a fractional offset
    # derived from the socket index, so that multiple links to the same node
    # produce distinct, correctly ordered weights.
    #
    # We store raw (neighbour_node, socket_fraction) pairs per node per
    # direction and resolve them during each sweep once column order is known.

    # link records: for each layoutable node, collect tuples of
    #   (neighbour_node, socket_fraction)
    # keyed by which side the neighbour is on (left or right).
    left_links: dict[bpy.types.Node, list[tuple[bpy.types.Node, float]]] = {
        n: [] for n in layoutable
    }
    right_links: dict[bpy.types.Node, list[tuple[bpy.types.Node, float]]] = {
        n: [] for n in layoutable
    }

    for link in tree.links:
        src, dst = link.from_node, link.to_node
        if src not in layoutable or dst not in layoutable:
            continue
        src_col, dst_col = col_of[src], col_of[dst]
        if src_col >= dst_col:
            continue  # only consider forward edges

        # Weight based on socket position on the neighbour node.
        # For a node in the right column looking left: the relevant socket is
        # on the source node (output side).
        # For a node in the left column looking right: the relevant socket is
        # on the target node (input side).
        out_count = max(1, sum(1 for s in src.outputs if s.enabled))
        in_count = max(1, sum(1 for s in dst.inputs if s.enabled))
        assert link.from_socket is not None and link.to_socket is not None
        src_frac = _socket_index(link.from_socket) / out_count
        dst_frac = _socket_index(link.to_socket) / in_count

        # dst looks left towards src: weight by src's output socket position
        left_links[dst].append((src, src_frac))
        # src looks right towards dst: weight by dst's input socket position
        right_links[src].append((dst, dst_frac))

    for iteration in range(passes):
        if iteration % 2 == 0:
            # forward sweep: fix column i, sort column i+1
            col_range = range(1, len(columns))
        else:
            # backward sweep: fix column i, sort column i-1
            col_range = range(len(columns) - 2, -1, -1)

        for ci in col_range:
            if iteration % 2 == 0:
                fixed_col = columns[ci - 1]
                links_map = left_links
            else:
                fixed_col = columns[ci + 1]
                links_map = right_links

            pos_in_fixed = {node: idx for idx, node in enumerate(fixed_col)}
            original_pos = {node: float(idx) for idx, node in enumerate(columns[ci])}

            barycenters: dict[bpy.types.Node, float] = {}
            for node in columns[ci]:
                weights = [
                    pos_in_fixed[nb] + frac
                    for nb, frac in links_map[node]
                    if nb in pos_in_fixed
                ]
                if weights:
                    barycenters[node] = sum(weights) / len(weights)
                else:
                    barycenters[node] = original_pos[node]

            columns[ci].sort(key=lambda n: barycenters[n])


def position_nodes_in_columns(
    columns: list[list[bpy.types.Node]],
    connection_counts: Counter,
    spacing: tuple[float, float] = (50, 25),
) -> None:
    """Position nodes column-by-column with the given spacing.

    Consecutive collapsed nodes are stacked tightly (with minimal gap) to
    keep related math/converter chains visually grouped together.
    """
    COLLAPSED_GAP = 4

    x = 0.0
    for column in columns:
        col_width = 0.0
        y = 0.0
        prev_hidden = False

        for node in column:
            node.update()

            width, height = calculate_node_dimensions(node, connection_counts, 1.0)

            col_width = max(col_width, width)

            node.location = (x, y)

            # use tight spacing between consecutive collapsed nodes
            if node.hide and prev_hidden:
                y -= height + COLLAPSED_GAP
            else:
                y -= height + spacing[1]

            prev_hidden = node.hide

        x += col_width + spacing[0]


def position_reroutes(tree: bpy.types.NodeTree) -> None:
    """Place reroute nodes midway between their source and target."""
    for node in tree.nodes:
        if node.bl_idname != "NodeReroute":
            continue

        sources: list[bpy.types.Node] = []
        targets: list[bpy.types.Node] = []
        for link in tree.links:
            if link.to_node == node:
                assert link.from_node is not None
                sources.append(link.from_node)
            if link.from_node == node:
                assert link.to_node is not None
                targets.append(link.to_node)

        neighbours = sources + targets
        if not neighbours:
            continue

        avg_x = sum(n.location.x for n in neighbours) / len(neighbours)
        avg_y = sum(n.location.y for n in neighbours) / len(neighbours)
        node.location = (avg_x, avg_y)


def arrange_tree(
    tree: bpy.types.NodeTree,
    spacing: tuple[float, float] = (50, 25),
) -> None:
    """Arrange nodes in a node tree based on their dependencies.

    Organises layoutable nodes into columns from left to right and positions
    reroute nodes between their neighbours.  Frame nodes are left untouched.
    """
    if not tree.nodes:
        return

    dependency_graph, connection_counts = build_dependency_graph(tree)

    if not dependency_graph:
        return

    nodes_in_order = topological_sort(dependency_graph)
    columns = organize_into_columns(nodes_in_order, dependency_graph)
    _reduce_crossings(columns, tree)
    position_nodes_in_columns(columns, connection_counts, spacing)
    position_reroutes(tree)
