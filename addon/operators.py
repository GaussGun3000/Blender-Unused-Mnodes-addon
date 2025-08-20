from typing import Set, Tuple

import bpy

class UnusedNodeOperator(bpy.types.Operator):
    bl_idname = "node.detect_unused_nodes"
    bl_label = "Detect Unused M-nodes"
    bl_description = "Finds unused material nodes and adds Attribute nodes to them (if applicable)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        total = self.process_all_materials()
        return {'FINISHED'}

    def _walk_to_output(self,
                        start_node: bpy.types.Node,
                        valid_outputs: Set[bpy.types.Node]) -> Tuple[bool, Set[bpy.types.Node]]:
        """
        Forward-walk from start_node following output links.
        Returns bool indicating whether node chain reaches output, and a set of visited nodes
        """
        stack = [start_node]
        visited = set()
        reaches = False

        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)

            if n in valid_outputs:
                reaches = True
                # don't early-return; still mark everyone we touched in this walk
                continue

            # push downstream neighbors
            for out in getattr(n, "outputs", []):
                if out.is_linked:
                    for link in out.links:
                        stack.append(link.to_node)

        return reaches, visited

    def classify_material_nodes(self, tree: bpy.types.NodeTree) -> Tuple[Set[bpy.types.Node], Set[bpy.types.Node]]:
        """
        Classify nodes in a MATERIAL node tree into (used, unused).
        A node is 'used' if there's a forward path to an (active) Material Output.
        """
        if tree is None:
            return set(), set()

        nodes = set(tree.nodes)

        outputs = [n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL']
        active = [n for n in outputs if getattr(n, "is_active_output", False)]
        valid_outputs = set(active if active else outputs)

        if not valid_outputs:
            return set(), nodes

        unclassified = set(nodes)
        used: Set[bpy.types.Node] = set()
        unused: Set[bpy.types.Node] = set()

        while unclassified:
            start = unclassified.pop()
            reaches, visited = self._walk_to_output(start, valid_outputs)
            if reaches:
                used.update(visited)
            else:
                unused.update(visited)
            unclassified.difference_update(visited)

        return used, unused

    def process_all_materials(self) -> int:
        """Iterate over all materials, classify nodes, and report results"""
        total_unused = 0
        for mat in bpy.data.materials:
            if not (mat and mat.use_nodes and mat.node_tree):
                continue
            used, unused = self.classify_material_nodes(mat.node_tree)
            self._report_material_result(mat, unused)
            total_unused += len(unused)

        self.report({'INFO'}, f"Total unused nodes: {total_unused}" if total_unused else "No unused nodes found.")
        return total_unused

    def _report_material_result(self, mat, unused_nodes) -> None:
        """Output unused node info for a material."""
        if not unused_nodes:
            self.report({'INFO'}, f"[Material: {mat.name}] No unused nodes.")
            print(f"[Material: {mat.name}] No unused nodes.")
            return

        self.report({'INFO'}, f"[Material: {mat.name}] Unused nodes ({len(unused_nodes)}):")
        print(f"[Material: {mat.name}] Unused nodes ({len(unused_nodes)}):")
        for n in sorted(unused_nodes, key=lambda x: x.name):
            self.report({'INFO'}, f"{n.name} (type={n.type})")
            print(f"  - {n.name} (type={n.type})")
