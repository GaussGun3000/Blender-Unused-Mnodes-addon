from typing import Set, Tuple, Union, List

import bpy
from addon.group_nodeinspector import GroupNodeInspector
from addon.framer import Framer

class UnusedNodeOperator(bpy.types.Operator):
    bl_idname = "node.detect_unused_nodes"
    bl_label = "Detect Unused M-nodes"
    bl_description = "Finds unused material nodes and adds Attribute nodes to them (if applicable)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        self._group_inspector = GroupNodeInspector(self.attach_attribute_nodes, self)
        total = self.process_all_materials()
        return {'FINISHED'}

    def attach_attribute_nodes(self, node_tree: bpy.types.NodeTree,
                               nodes:  Union[Set[bpy.types.Node], List[bpy.types.Node]]) -> None:
        """
        For each node in `nodes`, if it has at least one free input,
        attach a Shader 'Attribute' node to the left and link it.
        Skips outputs and frames.
        """
        SKIP_NODE_TYPES = {"OUTPUT_MATERIAL", "GROUP_OUTPUT", "FRAME"}
        ATTR_NAME =  "Auto Attribute"

        new_nodes = set() if isinstance(nodes, set) else list()
        for n in nodes:
            if not node_tree or not n:
                continue
            if n.type in SKIP_NODE_TYPES:
                continue

            free_inputs = [inp for inp in getattr(n, "inputs", [])
                           if not inp.is_linked]
            if not free_inputs:
                continue

            attr = node_tree.nodes.new("ShaderNodeAttribute")
            attr.label = ATTR_NAME
            attr.location = (n.location.x - 200, n.location.y)

            if attr.outputs and free_inputs:
                try:
                    node_tree.links.new(attr.outputs[0], free_inputs[0])
                    new_nodes.add(attr) if isinstance(nodes, set) else new_nodes.append(attr)
                except Exception as e:
                    print(f"Exception when attaching Attribute {e}, skipping")
                    node_tree.nodes.remove(attr)
        if isinstance(nodes, set):
            nodes.update(new_nodes)
        else:
            nodes.extend(new_nodes)

    def evaluate_node(self,
                      node: bpy.types.Node,
                      valid_outputs: set) -> tuple[bool, list]:
        """
        Evaluate a single node:
          - returns (reaches_output_here, downstream_neighbors)
          - if node is a GROUP, evaluate the group and its NodeTree
        Does NOT mutate traversal state beyond GROUP bookkeeping.
        """
        if node in valid_outputs:
            return True, []

        if node.type == 'GROUP' and getattr(node, "node_tree", None):
            self._group_inspector.inspect_group(node.node_tree)

        # downstream neighbors from all linked outputs
        neighbors = []
        for out in getattr(node, "outputs", []):
            if out.is_linked:
                for link in out.links:
                    neighbors.append(link.to_node)

        return False, neighbors

    def _walk_to_output(self,
                        start_node: bpy.types.Node,
                        valid_outputs: Set[bpy.types.Node]) -> Tuple[bool, Set[bpy.types.Node]]:
        """
        Forward-walk from start_node following output links.
        Returns bool indicating whether node chain reaches output, and a set of visited nodes
        """
        stack = [start_node]
        visited = set()
        reaches_any_output = False

        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)

            reaches_here, next_nodes = self.evaluate_node(n, valid_outputs)
            if reaches_here:
                reaches_any_output = True

            for nn in next_nodes:
                if nn not in visited:
                    stack.append(nn)

        return reaches_any_output, visited

    def classify_material_nodes(self, tree: bpy.types.NodeTree) -> Tuple[Set[bpy.types.Node], Set[bpy.types.Node]]:
        """
        Classify nodes in a MATERIAL node tree into (used, unused).
        A node is 'used' if there's a forward path to an active Material Output.
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
            self.attach_attribute_nodes(mat.node_tree, unused)
            Framer.frame_unused_nodes(mat.node_tree, used, unused)
            self._report_material_result(mat, unused)
            total_unused += len(unused)

        total_unused += self._group_inspector.total_internal_unused
        self.report({'INFO'}, f"Total unused nodes: {total_unused}" if total_unused else "No unused nodes found.")
        return total_unused

    def _report_material_result(self, mat, unused_nodes) -> None:
        """Output unused node info for a material."""
        if not unused_nodes:
            self.report({'INFO'}, f"[Material: {mat.name}] No unused nodes.")
            print(f"[Material: {mat.name}] No unused nodes.")
            return

        rmsg = f"[Material: {mat.name}] Unused nodes ({len(unused_nodes)}):"
        print(f"[Material: {mat.name}] Unused nodes ({len(unused_nodes)}):")
        for n in sorted(unused_nodes, key=lambda x: x.name):
            rmsg += f"\n - {n.name} (type={n.type})"
            print(f"  - {n.name} (type={n.type})")

        self.report({'INFO'}, rmsg)
