from typing import Callable, Iterable, Set, Dict, List
import bpy
from addon.framer import Framer

class GroupNodeInspector:
    """
    Helper to analyze GROUP node usage across materials and inside the group itself.
    Public methods:
        inspectGroup(group_tree, classify_material_nodes_fn)
    """
    def __init__(self, attach_attribute_nodes: Callable, reporter_op: bpy.types.Operator | None = None):
        self._op = reporter_op
        self.attach_attribute_nodes = attach_attribute_nodes
        self._visited_group_trees: Set[bpy.types.NodeTree] = set()
        self._usage_cache: dict[bpy.types.NodeTree, tuple[list[str], list[str]]] = {}
        self._group_internal_cache: dict[bpy.types.NodeTree, tuple[Set[bpy.types.Node], Set[bpy.types.Node]]] = {}
        self.total_internal_unused = 0

    def inspect_group(self, group_tree: bpy.types.NodeTree) -> None:
        if not group_tree:
            return

        if group_tree in self._visited_group_trees:
            return

        try:
            self._visited_group_trees.add(group_tree)
            used_in, present_unused_in = self._materials_usage_for_group(group_tree)
            used_g, unused_g = self._classify_group_nodes(group_tree)
            self.attach_attribute_nodes(group_tree, unused_g)
            Framer.frame_unused_nodes(group_tree, used_g, unused_g)
            self.total_internal_unused += len(unused_g)
            self._report_group_summary(group_tree, used_in, present_unused_in, unused_g)
        except Exception as e:
            print("Unhandled exception at GroupNodeInspector.inspect_group:", e)

    def _materials_usage_for_group(self, group_tree: bpy.types.NodeTree) -> tuple[list[str], list[str]]:
        """
        Find materials Group is used in
        """
        if group_tree in self._usage_cache:
            return self._usage_cache[group_tree]

        used_in: List[str] = []
        present_unused_in: List[str] = []

        for mat in bpy.data.materials:
            if not (mat and mat.use_nodes and mat.node_tree):
                continue

            # find all GROUP nodes referencing this datablock
            gnodes = [n for n in mat.node_tree.nodes
                      if n.type == 'GROUP' and getattr(n, "node_tree", None) is group_tree]
            if not gnodes:
                continue

            used, unused = self._classify_material_nodes_shallow(mat.node_tree)

            if any(n in used for n in gnodes):
                used_in.append(mat.name)
            else:
                present_unused_in.append(mat.name)

        self._usage_cache[group_tree] = (used_in, present_unused_in)
        return used_in, present_unused_in


    def _classify_material_nodes_shallow(self, tree: bpy.types.NodeTree) -> tuple[Set[bpy.types.Node], Set[bpy.types.Node]]:
        """
        Split nodes into used and unused in a material. Used to determine if Group instance is used in a material.
        """
        nodes = set(tree.nodes)
        outs = [n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL']
        act = [n for n in outs if getattr(n, "is_active_output", False)]
        valid_outputs = set(act if act else outs)
        if not valid_outputs:
            return set(), nodes

        unclassified = set(nodes)
        used, unused = set(), set()

        while unclassified:
            start = unclassified.pop()
            reaches, visited = self._forward_walk_no_group(start, valid_outputs)
            (used if reaches else unused).update(visited)
            unclassified.difference_update(visited)
        return used, unused

    def _forward_walk_no_group(self,
                               start_node: bpy.types.Node,
                               valid_outputs: Iterable[bpy.types.Node]) -> tuple[bool, Set[bpy.types.Node]]:
        """
        Forward DFS following output links.
        """
        stack = [start_node]
        visited: Set[bpy.types.Node] = set()
        reaches = False
        valid = set(valid_outputs)

        while stack:
            n = stack.pop()
            if n in visited:
                continue
            visited.add(n)

            if n in valid:
                reaches = True
                continue

            if n.type == 'GROUP' and getattr(n, "node_tree", None):
                self.inspect_group(n.node_tree)

            for out in getattr(n, "outputs", []):
                if out.is_linked:
                    for link in out.links:
                        stack.append(link.to_node)
        return reaches, visited


    def _classify_group_nodes(self, group_tree: bpy.types.NodeTree) -> tuple[Set[bpy.types.Node], Set[bpy.types.Node]]:
        """
        Split all nodes within the group into used and unused Sets
        :return:
        """
        if group_tree in self._group_internal_cache:
            return self._group_internal_cache[group_tree]

        nodes = set(group_tree.nodes)
        outs = [n for n in group_tree.nodes if n.type == 'GROUP_OUTPUT']
        if not outs:
            res = (set(), nodes)
            self._group_internal_cache[group_tree] = res
            return res

        valid = set(outs)
        unclassified = set(nodes)
        used, unused = set(), set()

        while unclassified:
            start = unclassified.pop()
            reaches, visited = self._forward_walk_no_group(start, valid)
            (used if reaches else unused).update(visited)
            unclassified.difference_update(visited)

        res = (used, unused)
        self._group_internal_cache[group_tree] = res
        return res

    def _report_group_summary(self,
                              group_tree: bpy.types.NodeTree,
                              used_in: List[str],
                              present_unused_in: List[str],
                              unused_internal: Set[bpy.types.Node]) -> None:
        msg = f"[Group: {group_tree.name}]\n"
        # --- materials referencing this group ---
        if not used_in and not present_unused_in:
            msg = "Group node is found in:\n  — no materials reference this group."
        else:
            refs = ["Group node is found in:"]
            refs += [f"  {name}, used" for name in sorted(used_in)]
            refs += [f"  {name}, unused" for name in sorted(present_unused_in)]
            msg += "\n".join(refs)

        self._output(msg)

        # --- internal unused nodes ---
        if unused_internal:
            unused_lines = [f"{group_tree.name} - internal unused nodes:"]
            unused_lines += [f"  - {n.name} (type={n.type})"
                             for n in sorted(unused_internal, key=lambda x: x.name)]
            self._output("\n".join(unused_lines))

    def _output(self, msg: str) -> None:
        """
        Outputs message into console and _op
        :param msg: Message to print
        """
        print(msg)
        if self._op is not None:
            try:
                self._op.report({'INFO'}, msg)
            except Exception as e:
                print(f"Exception on output from GroupNodeInspector: {e}")