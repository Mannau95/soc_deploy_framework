"""SOC Deploy Framework."""

import sys

# Support UTF-8 sous Windows sans plantage cp1252
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

__version__ = "0.1.0"
