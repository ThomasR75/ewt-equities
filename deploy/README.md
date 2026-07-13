---
title: EWT Dashboard
emoji: 📈
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Elliott-Wave calibration dashboard — read-only cloud view

Password-gated, read-only deployment of the EWT calibration platform. It serves
the precomputed state (`calib/calib_state.pkl`) and does live calibration, the
historic technicals, fundamentals display, and the zoomable charts. The wave
fitter, fundamentals refresh, and backtest are disabled here (run those locally).

Set two **Secrets** in the Space settings: `HOSTED_USER` and `HOSTED_PASS`.
