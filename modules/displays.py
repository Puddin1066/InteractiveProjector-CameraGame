"""Finds the projector among the connected displays."""
import os
import sys

from screeninfo import get_monitors


def projector_monitor():
    """The HDMI projector display chosen by PROJECTOR_MONITOR_INDEX (default 1)"""
    monitors = get_monitors()
    requested = int(os.getenv("PROJECTOR_MONITOR_INDEX", "1"))
    if 0 <= requested < len(monitors):
        monitor = monitors[requested]
        print(f"HDMI projector display {requested}: {monitor.width}x{monitor.height}")
        return monitor

    print(f"HDMI projector display {requested} is not connected. "
          f"Detected {len(monitors)} display(s).")
    print("Connect the projector over HDMI. The game is drawn on that display.")
    for index, monitor in enumerate(monitors):
        name = getattr(monitor, "name", "") or "display"
        print(f"  Display {index}: {name} {monitor.width}x{monitor.height}")
    sys.exit(1)
