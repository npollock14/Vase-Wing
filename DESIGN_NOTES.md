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
