import os, subprocess

BLENDER_EXE  = r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
PROJECT_DIR  = os.path.dirname(os.path.abspath(__file__))
BOOTSTRAP    = os.path.join(PROJECT_DIR, "blender-bootstrap.py")

subprocess.run([
    BLENDER_EXE,
    "--factory-startup",
    "--verbose", "4",
    "--python", BOOTSTRAP,
], check=False)
