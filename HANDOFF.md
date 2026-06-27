# Vase-Wing Handoff

Date: 2026-06-27

## Current Goal

Reduce the 1000 mm mode 3 vase-wing weight while preserving printable vase-mode topology, smooth outer extents, and spar strength. The current design direction is distributed rib lightening using contour-following arch cutouts that stay 2 mm from the airfoil skin and avoid the spar keepout/moat.

## Known-Good Slicer Baseline

Use `config/prusa_core_one_hf04_vase_known_good.ini` through `config/vase_validation.json`. This profile was recreated from a PrusaSlicer app export without credentials and verified against the visually accepted known-good G-code.

Important slicer settings:

- `spiral_vase = 1`
- `slice_closing_radius = 0`
- `perimeters = 1`
- `fill_density = 0%`
- `top_solid_layers = 0`
- `bottom_solid_layers = 0`
- `external_perimeter_extrusion_width = 0.5`
- `perimeter_extrusion_width = 0.5`
- `perimeter_generator = arachne`
- `filament_density = 0`

The old generated CLI profile and the repo-local LW-PLA profile produced misleading weight/volume behavior for this calibration work. Do not use them for final comparisons unless intentionally testing slicer-profile sensitivity.

## Pipeline State

`scripts/build_wing_pipeline.py` now:

- defaults to the profile in `config/vase_validation.json` instead of preferring a stale generated profile
- runs a fast actual xmin/xmax G-code artifact gate after slicing
- writes `x_extent_artifact_test.json` and `x_extent_artifact_test.png` beside each G-code
- writes fresh `pipeline-summary.json` on both pass and extent-test failure
- uses short auto-generated artifact filenames (`wing.stl`, `wing.gcode`) inside descriptive output folders to avoid Windows/PrusaSlicer path-length write failures

The artifact gate is implemented in `scripts/test_gcode_x_extents.py`. It streams already-sliced ASCII G-code, bins extrusion by slicer layer, and fails on actual xmin/xmax spikes or local discontinuities. The known-good baseline has worst jumps under 0.2 mm; the default 2 mm thresholds catch support-station artifacts.

## Current Geometry Direction

Mode 3 arch lightening is in `lib/Grid-Void-Creator.scad` and `Vase-Wing.scad`.

Current parameters of interest:

- `mode3_arch_slot_count = 6`
- `mode3_arch_slot_gap_mm = 2`
- `mode3_arch_slot_skin_clearance_mm = 2`
- `mode3_arch_slot_contour_samples = 10` by default; recent run used `12`
- `spar_rib_no_go_clearance_mm = 0.6`
- `mode3_spar_support_stations_enabled = false` for the latest clean artifact run

The current generated contour arches are placed aft of the spar keepout. This preserves the 0.6 mm spar moat and avoids the earlier support-station xmin/xmax spikes. The tradeoff is that the six arches are distributed only in the aft usable chord interval, not across the leading/spar keepout region.

## Latest Passing Candidate

Command:

```powershell
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 2 --spar-moat-mm 0.6 --centerline-chord-samples 64 --lightening-pattern arch-slot --arch-slot-count 6 --arch-slot-gap-mm 2 --arch-slot-skin-clearance-mm 2 --arch-slot-contour-samples 12 --arch-slot-height-fraction 0.95 --arch-slot-min-height-mm 4 --no-spar-support-stations --openscad-timeout-seconds 120 --no-open-viewer
```

Output directory:

```text
generated/current_wing_gm3_le0p6_te2_moat0p6_leE0p6_teE0p6_teMin2_cS64_parch_ac6_ag2_clr2_ah0p95_amin4_ssOff_sections39/
```

Key outputs:

- `wing.stl`
- `wing.gcode`
- `pipeline-summary.json`
- `x_extent_artifact_test.png`
- `analysis/contour_arch_aft_six_midspan_section.png`
- `analysis/contour_arch_aft_six_sections.png`

Latest metrics:

- PrusaSlicer: pass
- `spiral_vase = 1`
- `slice_closing_radius = 0`
- filament used: `179060.81 mm`
- volume: `430.69 cm3`
- LW-PLA estimate: about `213.6 g`
- x-extent artifact test: pass
- worst extent jump: `0.244 mm`

Known-good visual baseline was `471.69 cm3`, so the latest contour-arch candidate saves about `40.99 cm3`, or roughly `20.3 g` at the configured LW-PLA density (`0.496 g/cm3`).

## What Was Learned

- The very low weights from earlier work were partly caused by the wrong slicer profile. Always compare with the known-good profile.
- Spar support stations create large periodic xmin/xmax spikes and currently fail the artifact gate. Keep them off until the station geometry is redesigned.
- Increasing spar moat clearance reduces weight, but the moat exists for spar strength. The current direction keeps the moat at `0.6 mm`.
- Making a few fixed arch slots very wide causes them to merge into one large hole. The current code instead generates multiple slots with a fixed web/gap.
- A naive full-contour slot across the spar region either skips too much geometry or produces ragged/merged openings. The current implementation places generated contour arches aft of the spar keepout.

## Recommended Next Steps

1. Visually inspect the latest `wing.gcode` in Prusa G-code Viewer and the two section PNGs listed above.
2. Decide whether aft-only contour arches are acceptable, or whether a separate leading-side contour arch should be added in front of the spar keepout.
3. If more weight reduction is needed, try increasing `--arch-slot-count` in the aft interval or reducing `--arch-slot-skin-clearance-mm` cautiously. Validate every run with the x-extent gate.
4. Consider adding a dedicated parameter for leading-side arches instead of forcing all arches into one count.
5. Before committing generated outputs, remember `generated/` is intentionally ignored; keep source/config/docs committed, not G-code/STL artifacts.

## Safety / Repo Notes

- `PrusaSlicer_config_bundle*.ini` is ignored because app exports can contain Prusa Connect or physical-printer credential fields.
- Do not commit generated artifacts unless the project policy changes.
- On Windows, avoid very long output filenames for PrusaSlicer. The pipeline now uses short `wing.stl` and `wing.gcode` for auto-named runs.