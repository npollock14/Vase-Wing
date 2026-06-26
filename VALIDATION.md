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

## Known-good slicer baseline

Confirmed by manual PrusaSlicer inspection:

- Source geometry: default `HEAD` `Vase-Wing.scad`.
- STL handling: raw OpenSCAD STL, no `clean_stl.py` cleanup.
- Print preset: `config/PrusaSlicer_config_bundle_physical_printers.ini` print settings.
- Important slicer setting: `slice_closing_radius = 0`.
- Vase mode: enabled, one perimeter, zero infill, zero top solid layers.
- Confirmed G-code: `generated/repro_gui_default_head_gapclose0/default_head_closest_gui_gapclose0.gcode`.

This baseline produced the expected internal ribs with voids and the center spar in place.
