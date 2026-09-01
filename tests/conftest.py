import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# MicroPython's `time` module has sleep_ms built in; CPython's doesn't.
# Patch it on the real module (not the library) so the import works and
# individual tests can still monkeypatch ebyte_e220_900t22d.sleep_ms to
# assert on delays without slowing the suite down.
if not hasattr(time, "sleep_ms"):
    time.sleep_ms = lambda ms: None
