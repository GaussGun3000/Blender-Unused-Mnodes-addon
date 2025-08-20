import bpy
from typing import Set, List, Union

UNUSED_FRAME_NAME = "UNUSED_NODES_FRAME_AUTO"
UNUSED_FRAME_LABEL = "Unused Nodes"

class Framer:
    @staticmethod
    def _bbox(nodes):
        nodes = [n for n in nodes if n]
        if not nodes:
            return None
        xs = [n.location.x for n in nodes]
        ys = [n.location.y for n in nodes]
        return (min(xs), min(ys), max(xs), max(ys))

    @staticmethod
    def frame_unused_nodes(tree: bpy.types.NodeTree,
                           used_nodes: Set[bpy.types.Node],
                           unused_nodes: Union[Set[bpy.types.Node], List[bpy.types.Node]],
                           pad_x: float = 240.0) -> bpy.types.Node | None:
        if not tree or not unused_nodes:
            return None

        unused_list = [n for n in unused_nodes if n and n.type != 'FRAME']
        if not unused_list:
            return None

        used_bb = Framer._bbox(used_nodes)
        unused_bb = Framer._bbox(unused_list)
        if not unused_bb:
            return None

        dx = 0.0
        if used_bb:
            _, _, used_maxx, _ = used_bb
            unused_minx, _, _, _ = unused_bb
            target_left = used_maxx + pad_x
            dx = max(0.0, target_left - unused_minx)

        if dx > 0.0:
            for n in unused_list:
                n.location.x += dx

        uminx, uminy, umaxx, umaxy = Framer._bbox(unused_list)
        frame = next((n for n in tree.nodes
                      if n.type == 'FRAME' and n.name == UNUSED_FRAME_NAME), None)
        if not frame:
            frame = tree.nodes.new("NodeFrame")
            frame.name = UNUSED_FRAME_NAME
            frame.label = UNUSED_FRAME_LABEL

        for n in unused_list:
            if n.parent is not frame:
                n.parent = frame

        frame.location = (uminx - 40.0, umaxy + 40.0)
        return frame
