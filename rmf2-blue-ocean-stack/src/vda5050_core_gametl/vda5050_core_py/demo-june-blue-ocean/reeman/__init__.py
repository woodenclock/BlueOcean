"""Reeman VDA5050 adapter (real robot only).

Order coordinates are master-frame (AutoXing); a similarity transform loaded from
the master's /transform converts them into the Reeman frame for dispatch and
converts mirrored poses back for publishing. With no valid transform, navigation
is blocked (a robot-frame pose under the master map_id would be a lie).

Concern split:
  bridge.py    — the reeman_bridge / spellbook imports
  transform.py — MasterFrameTransform + /transform loader + master-frame publish
  drive.py     — per-node drive (with rack-docking align approach)
  adapter.py   — ReemanAdapter wiring + main()
"""
