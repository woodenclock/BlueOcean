"""Reeman↔master (AutoXing) 2D similarity transform, loaded from /transform."""

from __future__ import annotations

import json
import math
import sys
import urllib.error

import vda5050_core_py as vda

from adapter_core.master_client import master_get


class MasterFrameTransform:
    """Robot-frame ↔ master-frame 2D similarity loaded from /transform."""

    source = "master:/transform"

    def __init__(self, tx: float, ty: float, theta: float, scale: float = 1.0):
        self.tx = float(tx)
        self.ty = float(ty)
        self.theta = float(theta)
        self.scale = float(scale)
        self._c = math.cos(self.theta)
        self._s = math.sin(self.theta)

    def to_master(self, x, y, theta=None):
        x = float(x)
        y = float(y)
        xm = self.scale * (self._c * x - self._s * y) + self.tx
        ym = self.scale * (self._s * x + self._c * y) + self.ty
        tm = None if theta is None else float(theta) + self.theta
        return xm, ym, tm

    def to_robot(self, x, y, theta=None):
        x = float(x) - self.tx
        y = float(y) - self.ty
        s = self.scale if self.scale else 1.0
        xr = (self._c * x + self._s * y) / s
        yr = (-self._s * x + self._c * y) / s
        tr = None if theta is None else float(theta) - self.theta
        return xr, yr, tr


def load_tf_from_master(adapter: str = "reeman") -> MasterFrameTransform | None:
    """Load robot→master transform from the master's /transform endpoint."""
    try:
        payload = master_get("/transform")
        tf = payload["adapters"][adapter]["robot_to_master"]
        map_name = payload["adapters"][adapter].get("map_name")
        out = MasterFrameTransform(
            tx=tf["tx"], ty=tf["ty"], theta=tf["theta"], scale=tf.get("scale", 1.0)
        )
        print(
            f"Transform from master /transform adapter={adapter!r} "
            f"map={map_name!r} tx={out.tx:.4f} ty={out.ty:.4f} "
            f"theta={out.theta:.6f} scale={out.scale:.6f}",
            file=sys.stderr,
        )
        return out
    except (
        urllib.error.URLError, OSError, ValueError, KeyError, TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Master /transform unavailable for adapter {adapter!r}: {exc}",
              file=sys.stderr)
        return None


def set_master_position(
    nav: vda.NavigationManager, agv: vda.AGVPosition, map_id: str
) -> None:
    """Sole ``set_agv_position`` call site — the published VDA5050 State must
    always carry a master-frame (AutoXing) agvPosition under the master map_id.
    Callers hand in coordinates already converted via the calibration transform
    (or produced directly in the master frame)."""
    agv.map_id = map_id
    nav.set_agv_position(agv)
