import bpy

class UNUSEDNODE_PT_Panel(bpy.types.Panel):
    bl_label = "Unused Node Tool"
    bl_idname = "UNUSEDNODE_PT_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tools"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == 'ShaderNodeTree'

    def draw(self, context):
        layout = self.layout
        layout.operator("node.detect_unused_nodes", icon='NODE')
