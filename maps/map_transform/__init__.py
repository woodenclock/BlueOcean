"""Reeman→AutoXing map-frame calibration for the VDA5050 demo adapters.

AutoXing's map frame is the master frame. At Reeman adapter init,
``init_map_transform`` fetches the current map + named waypoints from both
robots, matches shared waypoint names, and estimates a 2D similarity
transform with ``nudged``. See ``transform.py`` for the offline rule.
"""

from map_transform.transform import (
    CalibrationError,
    MapTransform,
    compute_transform,
    init_map_transform,
    load_transform_file,
)

__all__ = [
    "CalibrationError",
    "MapTransform",
    "compute_transform",
    "init_map_transform",
    "load_transform_file",
]
