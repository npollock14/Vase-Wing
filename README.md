# Vase-Wing
Vase Wing is an OpenSCAD vase-mode 3D printable wing generator.

## Table of Contents

- [About](#about)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## About

This project is still a work in progress.

Vase Wing is an OpenSCAD vase-mode 3D printable wing generator designed for creating wings for RC planes. It supports slicing with PrusaSlicer, Cura, and potentially other software.

The tool consists of several parts. For most users, opening the Vase-Wing.scad file in OpenSCAD should be sufficient to generate wings.

There is also a Python scraper that collects data from the m-selig (http://m-selig.ae.illinois.edu/ads/coord_database.html) database. It uses aerosandbox (https://github.com/peterdsharpe/AeroSandbox) to increase the number of points on the DAT file, resulting in smoother airfoils.

Additionally, I utilized the Perl script from https://github.com/guillaumef/openscad-airfoil to generate the necessary SCAD paths in the OpenSCAD scripts.

The wing construction technique was adapted from the Propeller Generator by BouncyMonkey, available here: https://www.thingiverse.com/thing:3506692

![Wing1](git-images/E-Wing-1.png)


![Wing2](git-images/E-Wing-2.png)


![Wing3](git-images/E-Wing-3.png)


![Wing4](git-images/T-Wing-1.png)


![Wing5](git-images/T-Wing-3.png)

## Installation

If you only want to create wings using the provided airfoils, install OpenSCAD. For fast and practical STL export, use a current OpenSCAD development snapshot with the Manifold backend enabled.

The validated command-line pipeline expects these Windows defaults:

- OpenSCAD Nightly: `C:\Program Files\OpenSCAD (Nightly)\openscad.exe`
- PrusaSlicer: `C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe`
- Prusa G-code Viewer: `C:\Program Files\Prusa3D\PrusaSlicer\prusa-gcodeviewer.exe`

For the scraper, you will need Python, BeautifulSoup, and aerosandbox.

Refer to https://github.com/guillaumef/openscad-airfoil for instructions on using the Perl script.

## Usage

-----------------------------------------------------------
This is a fairly complicated render so takes time in the normal OpenSCAD application. At this time there is a new geometry engine called Manifold that is being implemented that is easily 100x faster than the old CSG one but it is only available in the Developer builds at the moment. To use it do the following:

Install the newest Development Snapshot of OpenSCAD from here:
https://openscad.org/downloads.html#snapshots

Then go to Edit/Preferences in the menu
Click on Features icon
Select manifold checkbox 

-----------------------------------------------------------

To use the Vase-Wing.scad script, simply open it in OpenSCAD. You can customize various configurations.

First, update the "// Module for root airfoil polygon section" and add a reference for any airfoils found in the lib/openscad-airfoil folder that you want to use.

Next, modify the "// Wing airfoils" section. It allows you to specify three airfoils: one for the root, midsection, and tip. If you only want one airfoil, make them all the same.

Finally, update the "//Global Variables*//" section. Follow the comments to customize the wing's appearance.

### One-pass STL and G-code pipeline

For the current mode 3 vase-wing workflow, use the Python pipeline. It exports an STL with OpenSCAD Nightly using `--backend Manifold`, cleans the STL for PrusaSlicer, exports G-code, and opens Prusa G-code Viewer by default.

```powershell
python scripts\build_wing_pipeline.py --leading-threshold-mm 0.6 --trailing-threshold-mm 2 --centerline-chord-samples 64 --openscad-timeout-seconds 60
```

Useful options:

- `--leading-threshold-mm`: removes rib/grid cutters near the leading edge where the local airfoil is too thin.
- `--trailing-threshold-mm`: removes rib/grid cutters near the trailing edge where the local airfoil is too thin.
- `--centerline-trailing-min-airfoil-height-mm`: stops the center divider before the trailing edge gets too thin; default is `2`.
- `--centerline-chord-samples`: controls centerline chord sampling; the validated default is `64`.
- `--no-open-viewer`: skips launching Prusa G-code Viewer after slicing.

Generated artifacts are written under `generated/`, which is intentionally ignored by git.

### Mode 3 vase topology notes

Mode 3 is intended to preserve a single continuous vase-mode contour. Internal ribs, spar-hole keepouts, and centerline dividers should behave like skin-derived detours, not separate islands or T-junctions. See `DESIGN_NOTES.md` for the topology rules and spar moat guidance.

The centerline divider uses the generated airfoil slice table to interpolate the true upper/lower midpoint, then applies the same chord and washout transform as the wing. The wing skin washout pivot is kept in the unscaled 100 mm airfoil coordinate system so the outer chord scale applies exactly once.

### LW-PLA weight estimate

PrusaSlicer reports filament volume in the G-code footer. If the profile has no density set, estimate standard PLA mass as:

```text
grams = filament_cm3 * 1.24
```

For LW-PLA, this project currently uses a quick estimate of 60% lighter than standard PLA:

```text
lw_pla_grams = standard_pla_grams * 0.40
```


## License

Please see the "LICENSE" for for licence information. 


