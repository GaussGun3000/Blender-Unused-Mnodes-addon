import bpy
from . import operators
from . import ui

bl_info = {
    "name": "Dangling M-node detector",
    "author": "IVV",
    "version": (1, 0, 0),
    "blender": (4, 4, 0),
    "location": "3D View > Sidebar > My Panel",
    "description": "Script that detects dangling material nodes",
    "category": "Node",
}


classes = (
    operators.UnusedNodeOperator,
    ui.UNUSEDNODE_PT_Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
