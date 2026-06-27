# Vase Validation MVP

This repo includes a local validation loop for LW-PLA spiral-vase wing coupons.

Run:

```powershell
python scripts\run_vase_validation.py config\vase_validation.json
```

The pipeline:

1. Exports a short OpenSCAD coupon with OpenSCAD Nightly Manifold.
2. Slices it with PrusaSlicer CLI using `config/prusa_vase_core_one_lwpla.ini`.
3. Parses the generated G-code.
4. Verifies zero retractions and basic path continuity.
5. Tracks printed `min_x`, `max_x`, and chord width over Z.
6. Writes JSON, Markdown, and PNG outputs into `generated/`.

Important outputs:

- `generated/vase_validation_report.md`
- `generated/vase_validation_report.json`
- `generated/extent_plot.png`
- `generated/extrusion_xy_preview.png`

The extent plot is the fastest way to spot leading-edge or trailing-edge artifacts.
Sharp spikes or steps in `actual min X` usually indicate leading-edge issues.
Sharp spikes or steps in `actual max X` usually indicate trailing-edge issues.

The Prusa profile uses a virtual validation bed so wide coupons can be sliced for
analysis even when they would need rotation or segmentation for real printing.

## One-pass STL and G-code pipeline

Run the current mode 3 wing artifact build, clean the OpenSCAD STL, export G-code,
and open Prusa G-code Viewer:

```powershell
python scripts\build_wing_pipeline.py
```

The default build uses mode 3 arch-slot lightening, spar support stations, spar-moat 0.6, leading-entry 0.6, trailing-entry 0.6, trailing centerline minimum height 2.0, and centerline samples 64.
It writes to a generated folder whose name records the thresholds, pattern, and spar-station settings.

Useful overrides:

```powershell
python scripts\build_wing_pipeline.py --leading-threshold-mm 10
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 0.6
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 0.6 --centerline-trailing-min-airfoil-height-mm 2.5
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 0.6 --centerline-chord-samples 512
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 2 --lightening-pattern arch-slot --spar-support-stations
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 2 --lightening-pattern circle --spar-support-stations
python scripts\build_wing_pipeline.py --leading-threshold-mm 20 --no-open-viewer
python scripts\build_wing_pipeline.py --define mode3_centerline_gap_mm=0.65
```

The pipeline parses the G-code footer and writes `weight_estimate` into `pipeline-summary.json`. The repo-local LW-PLA profile uses `filament_density = 0.496`, matching the current 60% lighter-than-standard-PLA estimate.

## Known-good slicer baseline

Confirmed by manual PrusaSlicer inspection:

- Source geometry: default `HEAD` `Vase-Wing.scad`.
- STL handling: raw OpenSCAD STL, no `clean_stl.py` cleanup.
- Print preset: `config/PrusaSlicer_config_bundle_physical_printers.ini` print settings.
- Important slicer setting: `slice_closing_radius = 0`.
- Vase mode: enabled, one perimeter, zero infill, zero top solid layers.
- Confirmed G-code: `generated/repro_gui_default_head_gapclose0/default_head_closest_gui_gapclose0.gcode`.

This baseline produced the expected internal ribs with voids and the center spar in place.
