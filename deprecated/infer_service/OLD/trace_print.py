import builtins, traceback, sys
_real_print = builtins.print

def traced_print(*args, **kwargs):
    s = " ".join(str(a) for a in args)
    # match your pipeline prefix
    if s.startswith('filesrc location="') or " ! hailonet " in s:
        _real_print("\n=== PIPELINE PRINT STACK ===", file=sys.stderr)
        for line in traceback.format_stack(limit=20):
            _real_print(line.rstrip("\n"), file=sys.stderr)
        _real_print("=== END STACK ===\n", file=sys.stderr)
    return _real_print(*args, **kwargs)

builtins.print = traced_print

import runpy
runpy.run_path("/root/thesis_deprecated/infer_service/detection_zmq.py", run_name="__main__")
