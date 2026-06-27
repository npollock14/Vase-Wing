// RC wing generator for Vase mode printing
//
// Prior work used to create this script:
// https://www.thingiverse.com/thing:3506692
// https://github.com/guillaumef/openscad-airfoil

// Module for root airfoil polygon
include <lib/openscad-airfoil/n/naca2415.scad>

af_vec_path_root = airfoil_NACA2415_path();
af_vec_path_mid = airfoil_NACA2415_path();
af_vec_path_tip = airfoil_NACA2415_path();
af_vec_slice_root = airfoil_NACA2415_slice();
af_vec_slice_mid = airfoil_NACA2415_slice();
af_vec_slice_tip = airfoil_NACA2415_slice();

// Wing airfoils
module RootAirfoilPolygon()
{
    airfoil_NACA2415();
}

module MidAirfoilPolygon()
{
    airfoil_NACA2415();
}

module TipAirfoilPolygon()
{
    airfoil_NACA2415();
}

//*******************END***************************//

//****************Global Variables*****************//

$fa = 5; // 360deg/5($fa) = 60 facets this affects performance and object shoothness
$fs = 1; // Min facet size

slice_ext_width = 0.6;//Used for some of the interfacing and gap width values
slice_gap_width = 0.1;//This is the gap in the outer skin.(smaller is better but is limited by what your slicer can recognise)

wing_mode = 1; // 1=trapezoidal wing 2= elliptic wing

wing_sections =
    39; // how many sections you would like to break up the wing into more is higher resolution but higher processing
wing_mm = 1000;           // wing length in mm
wing_root_chord_mm = 280; // Root chord legth in mm
wing_tip_chord_mm = 240;  // wing tip chord length in mm (Not relevant for elliptic wing)

wing_center_line_perc = 28; // Percentage from the leading edge where you would like the wings center line

//****************Wing Airfoil settings**********//
center_airfoil_change_perc = 100; // Where you want to change to the center airfoil 100 is off
tip_airfoil_change_perc = 100;    // Where you want to change to the tip airfoil 100 is off
slice_transisions = 0; // This is the number of slices that will be a blend of airfiols when airfoil is changed 0 is off
//******//

//****************Wing Washout settings**********//
washout_deg = 2;         // how many degrees of washout you want 0 for none
washout_start = 0;       // where you would like the washout to start in mm from root
washout_pivot_perc = 28; // Where the washout pivot point is percent from LE
//******//

add_inner_grid = true; // true if you want to add the inner grid for 3d printing

grid_mode = 1;            // Grid mode 1=diamond 2=spar and cross spars 3=airfoil-centered diamond
create_rib_voids = false; // add holes to the ribs to decrease weight
trailing_edge_grid_keepout_mm = 1; // keep ribs/grid this far forward of the local trailing edge

//****************Grid mode 1 settings**********//
grid_size_factor = 5.6; // changes the size of the inner grid blocks
//******//

//****************Grid mode 3 settings**********//
mode3_centerline_samples = 28;       // samples used for the airfoil-centered vase seam
mode3_centerline_gap_mm = slice_ext_width;
mode3_centerline_le_overshoot_mm = slice_ext_width;
mode3_centerline_te_overshoot_mm = slice_ext_width;
mode3_centerline_start_fraction = 0;
mode3_centerline_end_fraction = 1;
mode3_centerline_trailing_min_airfoil_height_mm = 2;
mode3_centerline_chord_samples = 64;
mode3_skin_clearance_mm = 0.6;       // clearance from the skin for lightening holes
mode3_lightening_holes = true;       // add spanwise circular rib lightening holes
mode3_lightening_chord_fractions = [ 0.16, 0.45, 0.62 ];
mode3_lightening_radius_fraction = 0.35;
mode3_lightening_min_radius_mm = 3;
mode3_lightening_max_radius_mm = 10;
mode3_spar_lightening_keepout_mm = 24;
mode3_airfoil_sample_tolerance_mm = 1.5;
//******//

//****************Rib thin-zone settings**********//
rib_thin_zone_enabled = true;   // remove rib/grid cutters where the airfoil is too thin for vase topology
rib_min_airfoil_height_mm = 6; // legacy fallback for older overrides
rib_leading_thin_zone_enabled = true;
rib_trailing_thin_zone_enabled = true;
rib_leading_min_airfoil_height_mm = 4;
rib_trailing_min_airfoil_height_mm = 10;
rib_skin_clearance_mm = 1.2;
rib_thin_zone_blend_mm = 2; // legacy fallback for older overrides
rib_leading_thin_zone_blend_mm = 1;
rib_trailing_thin_zone_blend_mm = 2;
rib_thin_zone_chord_samples = 64;
//******//

//****************Grid mode 2 settings**********//
spar_num = 3;     // Number of spars for grid mode 2
spar_offset = 15; // Offset the spars from the LE/TE
rib_num = 6;      // Number of ribs
rib_offset = 1;   // Offset
//******//

//****************Carbon Spar settings**********//
spar_hole = true;                // Add a spar hole into the wing
spar_hole_perc = 28;             // Percentage from leading edge
spar_hole_size = 14.2;           // Size of the spar hole
spar_hole_length = 1000;         // lenth of the spar in mm
spar_hole_offset = 5;            // Adjust where the spar is located
spar_hole_void_clearance = 1; // Clearance for the spar to grid interface(at least double extrusion width is usually needed)
spar_rib_no_go_enabled = true; // Keep mode 3 ribs from touching the spar-hole contour in vase mode
spar_rib_no_go_clearance_mm = 0.6;
//******//

//****************Servo settings**********//
create_servo_void = true; // It is important to check that your servo placement doesnt create any artifacts(You can
// comment out the CreateWing() function to assist)
servo_type = 4;           // 1=3.7g 2=5g 3=9g 4=KST X10 Mini
servo_dist_root_mm = 250; // servo placement from root
servo_dist_le_mm = 185;   // servo placement from the leading edge
servo_rotate_z_deg = -2;  // degrees to rotate on z axis
servo_dist_depth_mm = 0;  // offset the servo into or out of the wing till you dont see red
servo_show = false;       // for debugging only. Show the servo for easier placement
//******//

//****************Aileron settings**********//
create_aileron = false; // Create an Aileron
aileron_root_width = 30;    //The aileron width from the TE on the root side
aileron_tip_width = 30;    //The aileron width from the TE on the tip side
aileron_length = 100;      //How long to make the aileron
aileron_start = 150;        //How far from the root should the aileron start
//******//

//*******************END***************************//

include <lib/Grid-Structure.scad>
include <lib/Grid-Void-Creator.scad>
include <lib/Helpers.scad>
include <lib/Rib-Void-Creator.scad>
include <lib/Servo-Hole.scad>
include <lib/Spar-Hole.scad>
include <lib/Wing-Creator.scad>
include <lib/Aileron-Creator.scad>

module main()
{
    difference()
    {
        difference()
        {
            CreateWing();

            if (add_inner_grid)
            {
                union()
                {
                    difference()
                    {
                        difference()
                        {
                            if (grid_mode == 1 || grid_mode == 3)
                            {
                                StructureGrid(wing_mm, wing_root_chord_mm, grid_size_factor);
                            }
                            else
                            {
                                StructureSparGrid(wing_mm, wing_root_chord_mm, grid_size_factor, spar_num, spar_offset,
                                                  rib_num, rib_offset);
                            }
                            union()
                            {
                                if (grid_mode == 1)
                                {
                                    if (create_rib_voids)
                                    {
                                        CreateRibVoids();
                                    }
                                }
                                else if (grid_mode == 3)
                                {
                                    if (mode3_lightening_holes)
                                    {
                                        CreateMode3LighteningVoids();
                                    }
                                    if (spar_hole && spar_rib_no_go_enabled)
                                    {
                                        CreateMode3SparRibNoGoVoid();
                                    }
                                }
                                else
                                {
                                    if (create_rib_voids)
                                    {
                                        CreateRibVoids2();
                                    }
                                }
                                union()
                                {
                                    if (spar_hole && grid_mode != 3)
                                    {
                                        CreateSparVoid();
                                    }
                                    if (create_servo_void)
                                    {
                                        rotate([ 0, 0, servo_rotate_z_deg ])
                                            translate([ servo_dist_le_mm, servo_dist_depth_mm, servo_dist_root_mm ])
                                        {
                                            if (servo_type == 1)
                                            {
                                                3_7gServoVoid();
                                            }
                                            else if (servo_type == 2)
                                            {
                                                5gServoVoid();
                                            }
                                            else if (servo_type == 3)
                                            {
                                                9gServoVoid();
                                            }
                                            else if (servo_type == 4)
                                            {
                                                KSTX10MiniServoVoid();
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        if (grid_mode == 3)
                        {
                            CreateMode3GridVoid();
                            if (rib_thin_zone_enabled)
                            {
                                CreateRibThinZoneKeepout();
                            }
                        }
                        else
                        {
                            CreateGridVoid();
                        }
                        TrailingEdgeGridKeepoutVoid();
                    }
                }
            }
        }
        union()
        {
            if (spar_hole)
            {
                CreateSparHole();
            }
            if (create_servo_void)
            {
                rotate([ 0, 0, servo_rotate_z_deg ])
                    translate([ servo_dist_le_mm, servo_dist_depth_mm, servo_dist_root_mm ])
                {
                    if (servo_type == 1)
                    {
                        3_7gServo();
                    }
                    else if (servo_type == 2)
                    {
                        5gServo();
                    }
                    else if (servo_type == 3)
                    {
                        9gServo();
                    }
                    else if (servo_type == 4)
                    {
                        KSTX10MiniServo();
                    }
                }
            }
        }
    }
}

function TrailingEdgeXAtPosition(z_location) =
    let(chord = (wing_mode == 1) ? ChordLengthAtPosition(z_location)
                                 : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm, z_location))
        wing_root_chord_mm * (wing_center_line_perc / 100) + chord * (1 - wing_center_line_perc / 100);

module TrailingEdgeGridKeepoutVoid()
{
    if (trailing_edge_grid_keepout_mm > 0)
    {
        y_size = wing_root_chord_mm * 2;
        x_size = wing_root_chord_mm * 2;
        z_pad = 1;
        hull()
        {
            translate([ TrailingEdgeXAtPosition(0) - trailing_edge_grid_keepout_mm, -y_size / 2, -z_pad ])
                cube([ x_size, y_size, z_pad * 2 ]);
            translate([ TrailingEdgeXAtPosition(wing_mm) - trailing_edge_grid_keepout_mm, -y_size / 2, wing_mm - z_pad ])
                cube([ x_size, y_size, z_pad * 2 ]);
        }
    }
}

if (wing_sections * 0.2 < slice_transisions)
{
    echo("ERROR: You should lower the amount of slice_transisions.");
}
else if (center_airfoil_change_perc < 0 || center_airfoil_change_perc > 100)
{
    echo("ERROR: center_airfoil_change_perc has to be in a range of 0-100.");
}
else if (add_inner_grid == false && spar_hole == true)
{
    echo("ERROR: add_inner_grid needs to be true for spar_hole to be true");
}
else
{

    main();

    if (servo_show)
    {
        rotate([ 0, 0, servo_rotate_z_deg ]) translate([ servo_dist_le_mm, servo_dist_depth_mm, servo_dist_root_mm ])
        {
            if (servo_type == 1)
            {
                3_7gServo();
                //3_7gServoVoid();
            }
            else if (servo_type == 2)
            {
                5gServo();
                //5gServoVoid();
            }
            else if (servo_type == 3)
            {
                9gServo();
                //9gServoVoid();
            }
            else if (servo_type == 4)
            {
                KSTX10MiniServo();
                //KSTX10MiniServoVoid();
            }
        }
    }
}
