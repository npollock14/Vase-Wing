# Vase-Mode Topology Notes

## Single-Contour Clearance Topology

This wing is designed for true spiral/vase-mode LW-PLA printing. The slicer should see one continuous contour per layer, with no internal travel moves or retractions.

Internal ribs and spar features must act like maze-style detours of the contour, not separate islands, branches, T-junctions, or X-crossings. Nearby contour segments may be close enough to fuse after LW-PLA expansion, but they must remain separate in slicer topology.

For a 0.4 mm nozzle, use a controlled clearance target around `0.6 mm` between non-adjacent internal features. A practical test range is roughly `0.55 mm` to `0.75 mm`.

## Spar Moat Rule

The center spar hole must not be touched by diagonal ribs. If ribs terminate directly on the spar-hole contour, the layer can become a T-junction or ambiguous branch, which breaks true vase-mode slicing.

Mode 3 therefore keeps a configurable no-go moat around the spar hole:

```openscad
spar_rib_no_go_enabled = true;
spar_rib_no_go_clearance_mm = 0.6;
```

The nominal spar tube hole stays at `spar_hole_size`. The moat only clears rib/grid material around that hole so ribs stop before they can touch the spar contour.

## Protected Spar Support Stations

The wing can use a 14 mm OD carbon tube as the primary bending spar. Printed LW-PLA should transfer load into that tube at controlled stations, not through random rib endings along the whole spar hole.

Mode 3 support stations intentionally leave periodic bands through the spar no-go moat:

```openscad
mode3_spar_support_stations_enabled = true;
mode3_spar_support_station_spacing_mm = 125;
mode3_spar_support_station_width_mm = 12;
```

Between stations, the spar moat remains active. At stations, the grid may remain near the spar-hole contour so the final spar hole cut leaves a local printed support ring/saddle. Inspect these stations in the G-code viewer before printing; they are intentional load-transfer features and should not become disconnected islands or uncontrolled T-junctions.

## Arch-Slot Lightening

Arch-slot lightening replaces circular rib holes with elongated rounded windows:

```openscad
mode3_lightening_pattern = 1; // 0=circular holes, 1=rounded arch slots
mode3_arch_slot_width_mm = 6;
mode3_arch_slot_height_fraction = 0.85;
```

Rounded slots remove more rib/grid material than circles while preserving smoother load paths. They still respect skin clearance, spar keepout, and leading/trailing thin-zone gates.
