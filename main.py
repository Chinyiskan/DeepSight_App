import sys
import os
import multiprocessing

# Desactivar autoinstalaciones de pip en Ultralytics
os.environ["ULTRALYTICS_AUTO_INSTALL"] = "0"
os.environ["YOLO_VERBOSE"] = "False"

if __name__ == '__main__':
    multiprocessing.freeze_support()

    # Interceptar subprocesos de verificación lanzados por PyTorch / Ultralytics / Python
    if len(sys.argv) > 1:
        try:
            arg = sys.argv[1]
            if arg == '-c' and len(sys.argv) > 2:
                exec(sys.argv[2])
            elif arg == '-m' and len(sys.argv) > 2:
                mod_name = sys.argv[2]
                if mod_name != 'pip':
                    import runpy
                    runpy.run_module(mod_name, run_name='__main__')
        except Exception:
            pass
        sys.exit(0)

    from main_web import main
    main()


