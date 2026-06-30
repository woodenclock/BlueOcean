"""Autoxing L300 VDA5050 adapter (real robot only).

Concern split:
  bridge.py      — the autoxing_bridge / spellbook imports
  drive.py       — per-node plan / orient / drive pipeline
  actions.py     — HARD-blocking node actions (jackUp / jackDown)
  calibration.py — active-map log + stale-Reeman-calibration warning
  adapter.py     — AutoxingAdapter wiring + main()
"""
