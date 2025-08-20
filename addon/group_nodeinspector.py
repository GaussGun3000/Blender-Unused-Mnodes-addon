from typing import Callable, Iterable, Tuple, Set, Dict, List
import bpy

class GroupNodeInspector:
    """
    Helper to analyze GROUP node usage across materials and inside the group itself.
    Public methods:
        inspectGroup(group_tree, classify_material_nodes_fn)
    """
    def __init__(self, reporter_op: bpy.types.Operator | None = None):
        self._op = reporter_op
        self._visited_group_trees: Set[bpy.types.NodeTree] = set()
        self._usage_cache: dict[bpy.types.NodeTree, tuple[list[str], list[str]]] = {}
        self._group_internal_cache: dict[bpy.types.NodeTree, tuple[Set[bpy.types.Node], Set[bpy.types.Node]]] = {}

    def inspect_group(self, group_tree: bpy.types.NodeTree) -> None:
        if not group_tree:
            return

        if group_tree in self._visited_group_trees:
            return

        try:
            used_in, present_unused_in = self._materials_usage_for_group(group_tree)
            used_g, unused_g = self._classify_group_nodes(group_tree)
            self._report_group_summary(group_tree, used_in, present_unused_in, unused_g)
            self._visited_group_trees.add(group_tree)
        except Exception as e:
            print("Unhandled exception at GroupNodeInspector.inspect_group:", e)

    def _materials_usage_for_group(self, group_tree: bpy.types.NodeTree) -> tuple[list[str], list[str]]:
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

    # ------------- classify material (shallow; no group-inspection) -------------
    def _classify_material_nodes_shallow(self, tree: bpy.types.NodeTree) -> tuple[Set[bpy.types.Node], Set[bpy.types.Node]]:
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
            reaches, visited = self._forward_walk_no_group(tree, start, valid_outputs)
            (used if reaches else unused).update(visited)
            unclassified.difference_update(visited)
        return used, unused

    def _forward_walk_no_group(self,
                               tree: bpy.types.NodeTree,
                               start_node: bpy.types.Node,
                               valid_outputs: Iterable[bpy.types.Node]) -> tuple[bool, Set[bpy.types.Node]]:
        """Forward DFS following output links. GROUP nodes are treated like normal nodes (no inspector calls)."""
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

            for out in getattr(n, "outputs", []):
                if out.is_linked:
                    for link in out.links:
                        stack.append(link.to_node)
        return reaches, visited

    # ------------- classify inside the group (to GROUP_OUTPUT) -------------
    def _classify_group_nodes(self, group_tree: bpy.types.NodeTree) -> tuple[Set[bpy.types.Node], Set[bpy.types.Node]]:
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
            reaches, visited = self._forward_walk_no_group(group_tree, start, valid)
            (used if reaches else unused).update(visited)
            unclassified.difference_update(visited)

        res = (used, unused)
        self._group_internal_cache[group_tree] = res
        return res

    # ------------- reporting -------------
    def _report_group_summary(self,
                              group_tree: bpy.types.NodeTree,
                              used_in: List[str],
                              present_unused_in: List[str],
                              unused_internal: Set[bpy.types.Node]) -> None:
        self._say(f"[Group: {group_tree.name}]")
        self._say("Group node is found in:")
        if not used_in and not present_unused_in:
            self._say("  — no materials reference this group.")
        else:
            for name in sorted(used_in):
                self._say(f"  {name}, used")
            for name in sorted(present_unused_in):
                self._say(f"  {name}, unused")

        if unused_internal:
            self._say("Internal unused nodes:")
            for n in sorted(unused_internal, key=lambda x: x.name):
                self._say(f"  - {n.name} (type={n.type})")

    def _say(self, msg: str) -> None:
        print(msg)
        if self._op is not None:
            try:
                self._op.report({'INFO'}, msg)
            except Exception:
                pass