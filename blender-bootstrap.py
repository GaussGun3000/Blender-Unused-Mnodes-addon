import sys, os, importlib, traceback

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_MODULE = "addon"

def main():
    print("="*60)
    print("Bootstrap start")
    print("PROJECT_DIR:", PROJECT_DIR)
    print("ADDON_MODULE:", ADDON_MODULE)

    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
    print("sys.path[0:3]:", sys.path[:3])

    try:
        m = importlib.import_module(ADDON_MODULE)
        m = importlib.reload(m)
        print(f"Imported module: {m.__name__}")
    except Exception as e:
        print("!! import/reload failed:")
        traceback.print_exc()
        return

    if not hasattr(m, "register"):
        print("!! module has no register() – add register()/unregister() to __init__.py")
        return

    try:
        m.register()
        print(">> register() OK")
    except Exception:
        print("!! register() raised:")
        traceback.print_exc()
        return

    # sanity info
    try:
        bl_info = getattr(m, "bl_info", None)
        print("bl_info:", bl_info)
    except Exception:
        pass

    print("Bootstrap done")
    print("="*60)

if __name__ == "__main__":
    main()
