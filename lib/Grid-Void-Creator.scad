CamberAdjust = 0; //% to increase or decrease the camber for difficult airfoils
CenterGap = slice_ext_width;
XandZHeight = 0.0001;

//function scalePath(points, scaleFactor) = [for (p = points)[p[0] * scaleFactor, p[1] * scaleFactor]];

function max_x(points, idx = 0, max_vals = undef,
               max_x_val = -1e10) = (idx == len(points)) ? max_vals
                                    : (points[idx][0] > max_x_val)
                                        ? max_x(points, idx + 1, [points[idx]], points[idx][0])
                                    : (points[idx][0] == max_x_val)
                                        ? max_x(points, idx + 1, concat(max_vals, [points[idx]]), max_x_val)
                                        : max_x(points, idx + 1, max_vals, max_x_val);

function max_y(points, idy = 0, max_val = [ -1e10, -1e10 ]) =
    (idy == len(points)) ? max_val : max_y(points, idy + 1, points[idy][1] > max_val[1] ? points[idy] : max_val);

function min_x(points, idx = 0, min_val = [ 1e10, 1e10 ]) =
    (idx == len(points)) ? min_val : min_x(points, idx + 1, points[idx][0] < min_val[0] ? points[idx] : min_val);

function min_y(points, idy = 0, min_val = [ 1e10, 1e10 ]) =
    (idy == len(points)) ? min_val : min_y(points, idy + 1, points[idy][1] < min_val[1] ? points[idy] : min_val);

function get_y_center_point(points) =
    let(min_point = min_y(points),
        max_point = max_y(points))[(min_point[0] + max_point[0]) / 2, (min_point[1] + max_point[1]) / 2];

function trailing_edge_center(AFPoints) =
    let(trailing_points = max_x(AFPoints))[trailing_points[0][0], avg_y(trailing_points)];

function avg_y(points) = sum_y(points) / len(points);

function tail(points, idx = 1) = idx >= len(points) ? [] : concat([points[idx]], tail(points, idx + 1));

function sum_y(points) = len(points) == 0 ? 0 : points[0][1] + sum_y(tail(points));

function clamp_value(value, min_value, max_value) = min(max(value, min_value), max_value);

function y_values_near_x(points, distance, tolerance) = [for (pt = points) if (abs(pt[0] - distance) <= tolerance) pt[1]];

function airfoil_center_y_at_position(points, distance, tolerance) =
    let(y_values = y_values_near_x(points, distance, tolerance))
        len(y_values) == 0 ? 0 : (max(y_values) + min(y_values)) / 2;

function airfoil_height_at_position_safe(points, distance, tolerance) =
    let(y_values = y_values_near_x(points, distance, tolerance)) len(y_values) == 0 ? 0 : max(y_values) - min(y_values);

function airfoil_min_y_at_position_safe(points, distance, tolerance) =
    let(y_values = y_values_near_x(points, distance, tolerance)) len(y_values) == 0 ? 0 : min(y_values);

function airfoil_max_y_at_position_safe(points, distance, tolerance) =
    let(y_values = y_values_near_x(points, distance, tolerance)) len(y_values) == 0 ? 0 : max(y_values);

function airfoil_slice_clamped_x(slice_points, x_position) =
    clamp_value(x_position, slice_points[0][0], slice_points[len(slice_points) - 1][0]);

function interpolate_airfoil_slice_row(a, b, x_position) =
    abs(b[0] - a[0]) <= 0.000001
        ? a
        : let(t = (x_position - a[0]) / (b[0] - a[0]))[x_position, a[1] + t * (b[1] - a[1]),
                                                        a[2] + t * (b[2] - a[2])];

function airfoil_slice_row_at_x(slice_points, x_position, idx = 0) =
    let(clamped_x = airfoil_slice_clamped_x(slice_points, x_position))
        idx >= len(slice_points) - 1
            ? slice_points[len(slice_points) - 1]
            : clamped_x <= slice_points[idx + 1][0] + 0.000001
                ? interpolate_airfoil_slice_row(slice_points[idx], slice_points[idx + 1], clamped_x)
                : airfoil_slice_row_at_x(slice_points, clamped_x, idx + 1);

function airfoil_center_y_at_slice_position(slice_points, x_position) =
    let(row = airfoil_slice_row_at_x(slice_points, x_position)) (row[1] + row[2]) / 2;

function airfoil_height_at_slice_position(slice_points, x_position) =
    let(row = airfoil_slice_row_at_x(slice_points, x_position)) abs(row[1] - row[2]);

function airfoil_center_y_at_slice_fraction(slice_points, chord_fraction, current_chord_mm) =
    airfoil_center_y_at_slice_position(slice_points, 100 * clamp_value(chord_fraction, 0, 1)) * current_chord_mm / 100;

function airfoil_height_at_slice_fraction(slice_points, chord_fraction, current_chord_mm) =
    airfoil_height_at_slice_position(slice_points, 100 * clamp_value(chord_fraction, 0, 1)) * current_chord_mm / 100;

function Mode3AirfoilSliceForIndex(i) =
    i > wing_sections * (tip_airfoil_change_perc / 100)   ? af_vec_slice_tip
    : i > wing_sections * (center_airfoil_change_perc / 100) ? af_vec_slice_mid
                                                              : af_vec_slice_root;

function Mode3CenterlineChordFraction(sample_index) =
    clamp_value(sample_index / mode3_centerline_chord_samples, 0, 1);

function Mode3CenterlineSafeFractions(AFSlice, current_chord_mm, min_airfoil_height_mm) =
    min_airfoil_height_mm <= 0
        ? [ 0, 1 ]
        : [for (sample_index = [0:mode3_centerline_chord_samples])
              let(chord_fraction = Mode3CenterlineChordFraction(sample_index))
                  if (airfoil_height_at_slice_fraction(AFSlice, chord_fraction, current_chord_mm) >=
                      min_airfoil_height_mm)
                      chord_fraction];

function Mode3CenterlineTrailingEndFraction(AFSlice, current_chord_mm) =
    let(safe_fractions = Mode3CenterlineSafeFractions(AFSlice, current_chord_mm,
                                                      mode3_centerline_trailing_min_airfoil_height_mm))
        clamp_value(len(safe_fractions) == 0 ? mode3_centerline_start_fraction : max(safe_fractions),
                    mode3_centerline_start_fraction, mode3_centerline_end_fraction);

function Mode3ChordFractionX(current_chord_mm, sample_index, trailing_end_fraction) =
    let(use_trailing_overshoot = trailing_end_fraction >= mode3_centerline_end_fraction - 0.000001)
        sample_index <= 0
            ? -mode3_centerline_le_overshoot_mm
        : sample_index >= mode3_centerline_samples
            ? current_chord_mm * trailing_end_fraction + (use_trailing_overshoot ? mode3_centerline_te_overshoot_mm : 0)
            : let(fraction = mode3_centerline_start_fraction +
                             (trailing_end_fraction - mode3_centerline_start_fraction) * (sample_index - 1) /
                                 max(mode3_centerline_samples - 2, 1))
                  current_chord_mm * fraction;

function Mode3LighteningRadius(AFPoints, x_position) =
    let(airfoil_height = airfoil_height_at_position_safe(AFPoints, x_position, mode3_airfoil_sample_tolerance_mm),
        safe_radius = (airfoil_height - (2 * mode3_skin_clearance_mm)) / 2)
        max(0, min(safe_radius,
                   clamp_value(airfoil_height * mode3_lightening_radius_fraction, mode3_lightening_min_radius_mm,
                               mode3_lightening_max_radius_mm)));

function Mode3SparKeepoutFraction() = mode3_spar_lightening_keepout_mm / max(wing_root_chord_mm, 0.001);

function Mode3HoleClearsSpar(chord_fraction, current_chord_mm, half_width_mm) =
    !spar_hole ||
    ((abs(chord_fraction - (spar_hole_perc / 100)) * current_chord_mm) - half_width_mm) >
        mode3_spar_lightening_keepout_mm;

function RibThinZoneThreshold(min_airfoil_height_mm) =
    min_airfoil_height_mm <= 0 ? 0 : max(min_airfoil_height_mm, (rib_skin_clearance_mm * 2) + slice_ext_width);

function RibThinZoneChordFraction(sample_index) =
    clamp_value(sample_index / rib_thin_zone_chord_samples, 0, 1);

function RibThinZoneSafeFractions(AFPoints, current_chord_mm, min_airfoil_height_mm) =
    let(threshold = RibThinZoneThreshold(min_airfoil_height_mm))
        threshold <= 0
            ? [ 0, 1 ]
            : [for (sample_index = [0:rib_thin_zone_chord_samples])
                  let(chord_fraction = RibThinZoneChordFraction(sample_index))
                      if (airfoil_height_at_position_safe(AFPoints, current_chord_mm * chord_fraction,
                                                          mode3_airfoil_sample_tolerance_mm) >= threshold)
                          chord_fraction];

function RibThinZoneSafeMinFraction(AFPoints, current_chord_mm, min_airfoil_height_mm) =
    let(safe_fractions = RibThinZoneSafeFractions(AFPoints, current_chord_mm, min_airfoil_height_mm))
        len(safe_fractions) == 0 ? 0.5 : min(safe_fractions);

function RibThinZoneSafeMaxFraction(AFPoints, current_chord_mm, min_airfoil_height_mm) =
    let(safe_fractions = RibThinZoneSafeFractions(AFPoints, current_chord_mm, min_airfoil_height_mm))
        len(safe_fractions) == 0 ? 0.5 : max(safe_fractions);

function RibThinZoneLeadingEndFraction(AFPoints, current_chord_mm) =
    (!rib_thin_zone_enabled || !rib_leading_thin_zone_enabled || rib_leading_min_airfoil_height_mm <= 0)
        ? 0
        : clamp_value(RibThinZoneSafeMinFraction(AFPoints, current_chord_mm, rib_leading_min_airfoil_height_mm) -
                          (rib_leading_thin_zone_blend_mm / max(current_chord_mm, 0.001)),
                      0, 1);

function RibThinZoneTrailingStartFraction(AFPoints, current_chord_mm) =
    (!rib_thin_zone_enabled || !rib_trailing_thin_zone_enabled || rib_trailing_min_airfoil_height_mm <= 0)
        ? 1
        : clamp_value(RibThinZoneSafeMaxFraction(AFPoints, current_chord_mm, rib_trailing_min_airfoil_height_mm) +
                          (rib_trailing_thin_zone_blend_mm / max(current_chord_mm, 0.001)),
                      0, 1);

function Mode3LighteningClearsThinZones(AFPoints, current_chord_mm, chord_fraction, radius) =
    let(radius_fraction = radius / max(current_chord_mm, 0.001),
        hole_min_fraction = chord_fraction - radius_fraction,
        hole_max_fraction = chord_fraction + radius_fraction,
        leading_end_fraction = RibThinZoneLeadingEndFraction(AFPoints, current_chord_mm),
        trailing_start_fraction = RibThinZoneTrailingStartFraction(AFPoints, current_chord_mm))
        hole_min_fraction >= leading_end_fraction && hole_max_fraction <= trailing_start_fraction;

    function Mode3LighteningPatternIsArchSlot() = mode3_lightening_pattern == 1;
function Mode3GeneratedArchSlotsEnabled() = Mode3LighteningPatternIsArchSlot() && mode3_arch_slot_count > 0;

module CamberVoidLE(AFPoints)
{
    y_diff = max_y(AFPoints)[1] - min_y(AFPoints)[1];

    union()
    {
        color("red") hull()
        {
            translate(min_x(AFPoints)) cube([ XandZHeight, CenterGap, XandZHeight ], center = true);
            translate([ 0, (CamberAdjust / 100) * (y_diff / 2), 0 ]) translate(get_y_center_point(AFPoints))
                cube([ XandZHeight, CenterGap, XandZHeight ], center = true);
        }
    }
}

module CamberVoidTE(AFPoints)
{
    y_diff = max_y(AFPoints)[1] - min_y(AFPoints)[1];
    union()
    {
        color("blue") hull()
        {
            translate([ 0, (CamberAdjust / 100) * (y_diff / 2), 0 ]) translate(get_y_center_point(AFPoints))
                cube([ XandZHeight, CenterGap, XandZHeight ], center = true);
            translate(trailing_edge_center(AFPoints)) cube([ XandZHeight, CenterGap, XandZHeight ], center = true);
        }
    }
}

module Mode3CenterlinePoint(AFSlice, current_chord_mm, sample_index, trailing_end_fraction)
{
    x_position = Mode3ChordFractionX(current_chord_mm, sample_index, trailing_end_fraction);
    y_position = airfoil_center_y_at_slice_fraction(AFSlice, x_position / max(current_chord_mm, 0.001),
                                                    current_chord_mm);

    translate([ x_position, y_position, 0 ]) cube([ XandZHeight, mode3_centerline_gap_mm, XandZHeight ], center = true);
}

module Mode3CenterlinePointForCurrentAirfoil(i, current_chord_mm, sample_index, trailing_end_fraction)
{
    Mode3CenterlinePoint(Mode3AirfoilSliceForIndex(i), current_chord_mm, sample_index, trailing_end_fraction);
}

module Mode3CenterlineWashoutPoint(i, current_chord_mm, sample_index, trailing_end_fraction)
{
    washout_start_point = (wing_mode == 1) ? (wing_sections * (washout_start / 100))
                                           : WashoutStart(0, wing_sections, washout_start, wing_mm);
    washout_deg_frac = washout_deg / (wing_sections - washout_start_point);
    washout_deg_amount = (washout_start_point - i) * washout_deg_frac;
    rotate_point = current_chord_mm * (washout_pivot_perc / 100);

    translate([ rotate_point, 0, 0 ]) rotate(washout_deg_amount) translate([ -rotate_point, 0, 0 ])
        Mode3CenterlinePointForCurrentAirfoil(i, current_chord_mm, sample_index, trailing_end_fraction);
}

module Mode3CenterlineSlicePoint(z_location, i, sample_index, current_chord_mm, trailing_end_fraction)
{
    translate([ 0, 0, z_location ]) translate([ -wing_center_line_perc / 100 * current_chord_mm, 0, 0 ])
        if (washout_deg > 0 && ((wing_mode > 1 && i > WashoutStart(0, wing_sections, washout_start, wing_mm)) ||
                                (wing_mode == 1 && i > (wing_sections * (washout_start / 100)))))
    {
        Mode3CenterlineWashoutPoint(i, current_chord_mm, sample_index, trailing_end_fraction);
    }
    else
    {
        Mode3CenterlinePointForCurrentAirfoil(i, current_chord_mm, sample_index, trailing_end_fraction);
    }
}

module Mode3LighteningDisk(AFPoints, current_chord_mm, chord_fraction)
{
    x_position = current_chord_mm * chord_fraction;
    y_position = airfoil_center_y_at_position(AFPoints, x_position, mode3_airfoil_sample_tolerance_mm);
    radius = Mode3LighteningRadius(AFPoints, x_position);

    if (radius > 0 && Mode3HoleClearsSpar(chord_fraction, current_chord_mm, radius) &&
        Mode3LighteningClearsThinZones(AFPoints, current_chord_mm, chord_fraction, radius))
    {
        translate([ x_position, y_position, 0 ])
            cylinder(h = XandZHeight, r = radius, center = true, $fn = 24);
    }
}

module Mode3LighteningArchSlotAtX(AFPoints, current_chord_mm, x_position, slot_width)
{
    chord_fraction = x_position / max(current_chord_mm, 0.001);
    y_position = airfoil_center_y_at_position(AFPoints, x_position, mode3_airfoil_sample_tolerance_mm);
    airfoil_height = airfoil_height_at_position_safe(AFPoints, x_position, mode3_airfoil_sample_tolerance_mm);
    safe_height = airfoil_height - (2 * mode3_skin_clearance_mm);
    safe_slot_width = max(slot_width, mode3_lightening_min_radius_mm * 2);
    slot_height = min(safe_height, safe_height * mode3_arch_slot_height_fraction);
    corner_radius = min(safe_slot_width / 2, slot_height / 2, mode3_lightening_max_radius_mm);
    half_straight_x = max(0, (safe_slot_width / 2) - corner_radius);
    half_straight_y = max(0, (slot_height / 2) - corner_radius);

    if (safe_height >= mode3_arch_slot_min_height_mm && corner_radius >= mode3_lightening_min_radius_mm &&
        Mode3HoleClearsSpar(chord_fraction, current_chord_mm, safe_slot_width / 2) &&
        Mode3LighteningClearsThinZones(AFPoints, current_chord_mm, chord_fraction, safe_slot_width / 2))
    {
        translate([ x_position, y_position, 0 ]) hull()
        {
            for (dx = [ -half_straight_x, half_straight_x ])
            {
                for (dy = [ -half_straight_y, half_straight_y ])
                {
                    translate([ dx, dy, 0 ]) cylinder(h = XandZHeight, r = corner_radius, center = true, $fn = 18);
                }
            }
        }
    }
}

module Mode3LighteningArchSlot(AFPoints, current_chord_mm, chord_fraction)
{
    Mode3LighteningArchSlotAtX(AFPoints, current_chord_mm, current_chord_mm * chord_fraction,
                               mode3_arch_slot_width_mm);
}

function Mode3ContourSlotX(slot_start_x, slot_width, sample_index, sample_count) =
    slot_start_x + (slot_width * sample_index / max(sample_count, 1));

function Mode3ContourSlotUpperPoint(AFPoints, slot_start_x, slot_width, sample_index, sample_count, clearance) =
    let(x_position = Mode3ContourSlotX(slot_start_x, slot_width, sample_index, sample_count))
        [ x_position,
          airfoil_max_y_at_position_safe(AFPoints, x_position, mode3_airfoil_sample_tolerance_mm) - clearance ];

function Mode3ContourSlotLowerPoint(AFPoints, slot_start_x, slot_width, sample_index, sample_count, clearance) =
    let(x_position = Mode3ContourSlotX(slot_start_x, slot_width, sample_index, sample_count))
        [ x_position,
          airfoil_min_y_at_position_safe(AFPoints, x_position, mode3_airfoil_sample_tolerance_mm) + clearance ];

function Mode3ContourSlotInnerHeight(AFPoints, slot_start_x, slot_width, sample_index, sample_count, clearance) =
    let(upper = Mode3ContourSlotUpperPoint(AFPoints, slot_start_x, slot_width, sample_index, sample_count, clearance),
        lower = Mode3ContourSlotLowerPoint(AFPoints, slot_start_x, slot_width, sample_index, sample_count, clearance))
        upper[1] - lower[1];

module Mode3ContourArchSlotAtX(AFPoints, current_chord_mm, x_position, slot_width)
{
    clearance = max(mode3_skin_clearance_mm, mode3_arch_slot_skin_clearance_mm);
    sample_count = max(2, mode3_arch_slot_contour_samples);
    slot_start_x = x_position - (slot_width / 2);
    chord_fraction = x_position / max(current_chord_mm, 0.001);
    min_inner_height = min([for (sample_index = [0:sample_count])
                                Mode3ContourSlotInnerHeight(AFPoints, slot_start_x, slot_width, sample_index,
                                                            sample_count, clearance)]);

    if (slot_width >= mode3_lightening_min_radius_mm * 2 && min_inner_height >= mode3_arch_slot_min_height_mm &&
        Mode3HoleClearsSpar(chord_fraction, current_chord_mm, slot_width / 2) &&
        Mode3LighteningClearsThinZones(AFPoints, current_chord_mm, chord_fraction, slot_width / 2))
    {
        linear_extrude(height = XandZHeight, center = true, convexity = 10)
            polygon(points = concat(
                        [for (sample_index = [0:sample_count])
                             Mode3ContourSlotUpperPoint(AFPoints, slot_start_x, slot_width, sample_index, sample_count,
                                                        clearance)],
                        [for (sample_index = [sample_count:-1:0])
                             Mode3ContourSlotLowerPoint(AFPoints, slot_start_x, slot_width, sample_index, sample_count,
                                                        clearance)]));
    }
}

module Mode3GeneratedArchSlot(AFPoints, current_chord_mm, slot_index)
{
    slot_count = max(1, mode3_arch_slot_count);
    gap = max(0, mode3_arch_slot_gap_mm);
    leading_fraction = RibThinZoneLeadingEndFraction(AFPoints, current_chord_mm);
    trailing_fraction = RibThinZoneTrailingStartFraction(AFPoints, current_chord_mm);
    safe_start_x = current_chord_mm * leading_fraction;
    safe_end_x = current_chord_mm * trailing_fraction;
    spar_x = current_chord_mm * (spar_hole_perc / 100);
    spar_max_x = spar_x + mode3_spar_lightening_keepout_mm;
    interval_index = slot_index;
    interval_count = slot_count;
    interval_start_x = spar_hole ? max(safe_start_x, spar_max_x) : safe_start_x;
    interval_width = safe_end_x - interval_start_x;
    available_width = interval_width - (gap * max(interval_count - 1, 0));
    slot_width = interval_count <= 0 ? 0 : available_width / interval_count;
    x_position = interval_start_x + (slot_width / 2) + (interval_index * (slot_width + gap));

    if (slot_width >= mode3_lightening_min_radius_mm * 2)
    {
        Mode3ContourArchSlotAtX(AFPoints, current_chord_mm, x_position, slot_width);
    }
}

module Mode3LighteningVoid(AFPoints, current_chord_mm, chord_fraction)
{
    if (Mode3LighteningPatternIsArchSlot())
    {
        Mode3LighteningArchSlot(AFPoints, current_chord_mm, chord_fraction);
    }
    else
    {
        Mode3LighteningDisk(AFPoints, current_chord_mm, chord_fraction);
    }
}

module Mode3LighteningDiskForCurrentAirfoil(i, scale_factor, current_chord_mm, chord_fraction)
{
    if (i > wing_sections * (tip_airfoil_change_perc / 100))
    {
        Mode3LighteningVoid(scalePath(af_vec_path_tip, scale_factor), current_chord_mm, chord_fraction);
    }
    else if (i > wing_sections * (center_airfoil_change_perc / 100))
    {
        Mode3LighteningVoid(scalePath(af_vec_path_mid, scale_factor), current_chord_mm, chord_fraction);
    }
    else
    {
        Mode3LighteningVoid(scalePath(af_vec_path_root, scale_factor), current_chord_mm, chord_fraction);
    }
}

module Mode3GeneratedArchSlotForCurrentAirfoil(i, scale_factor, current_chord_mm, slot_index)
{
    if (i > wing_sections * (tip_airfoil_change_perc / 100))
    {
        Mode3GeneratedArchSlot(scalePath(af_vec_path_tip, scale_factor), current_chord_mm, slot_index);
    }
    else if (i > wing_sections * (center_airfoil_change_perc / 100))
    {
        Mode3GeneratedArchSlot(scalePath(af_vec_path_mid, scale_factor), current_chord_mm, slot_index);
    }
    else
    {
        Mode3GeneratedArchSlot(scalePath(af_vec_path_root, scale_factor), current_chord_mm, slot_index);
    }
}

module Mode3LighteningWashoutDisk(i, scale_factor, current_chord_mm, chord_fraction)
{
    washout_start_point = (wing_mode == 1) ? (wing_sections * (washout_start / 100))
                                           : WashoutStart(0, wing_sections, washout_start, wing_mm);
    washout_deg_frac = washout_deg / (wing_sections - washout_start_point);
    washout_deg_amount = (washout_start_point - i) * washout_deg_frac;
    rotate_point = current_chord_mm * (washout_pivot_perc / 100);

    translate([ rotate_point, 0, 0 ]) rotate(washout_deg_amount) translate([ -rotate_point, 0, 0 ])
        Mode3LighteningDiskForCurrentAirfoil(i, scale_factor, current_chord_mm, chord_fraction);
}

    module Mode3GeneratedArchSlotWashout(i, scale_factor, current_chord_mm, slot_index)
    {
        washout_start_point = (wing_mode == 1) ? (wing_sections * (washout_start / 100))
                           : WashoutStart(0, wing_sections, washout_start, wing_mm);
        washout_deg_frac = washout_deg / (wing_sections - washout_start_point);
        washout_deg_amount = (washout_start_point - i) * washout_deg_frac;
        rotate_point = current_chord_mm * (washout_pivot_perc / 100);

        translate([ rotate_point, 0, 0 ]) rotate(washout_deg_amount) translate([ -rotate_point, 0, 0 ])
        Mode3GeneratedArchSlotForCurrentAirfoil(i, scale_factor, current_chord_mm, slot_index);
    }

module Mode3LighteningSliceDisk(z_location, i, chord_fraction)
{
    current_chord_mm = (wing_mode == 1) ? ChordLengthAtIndex(i, wing_sections)
                                        : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm, z_location);
    scale_factor = current_chord_mm / 100;

    translate([ 0, 0, z_location ]) translate([ -wing_center_line_perc / 100 * current_chord_mm, 0, 0 ])
        if (washout_deg > 0 && ((wing_mode > 1 && i > WashoutStart(0, wing_sections, washout_start, wing_mm)) ||
                                (wing_mode == 1 && i > (wing_sections * (washout_start / 100)))))
    {
        Mode3LighteningWashoutDisk(i, scale_factor, current_chord_mm, chord_fraction);
    }
    else
    {
        Mode3LighteningDiskForCurrentAirfoil(i, scale_factor, current_chord_mm, chord_fraction);
    }
}

module Mode3GeneratedArchSlotSlice(z_location, i, slot_index)
{
    current_chord_mm = (wing_mode == 1) ? ChordLengthAtIndex(i, wing_sections)
                                        : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm, z_location);
    scale_factor = current_chord_mm / 100;

    translate([ 0, 0, z_location ]) translate([ -wing_center_line_perc / 100 * current_chord_mm, 0, 0 ])
        if (washout_deg > 0 && ((wing_mode > 1 && i > WashoutStart(0, wing_sections, washout_start, wing_mm)) ||
                                (wing_mode == 1 && i > (wing_sections * (washout_start / 100)))))
    {
        Mode3GeneratedArchSlotWashout(i, scale_factor, current_chord_mm, slot_index);
    }
    else
    {
        Mode3GeneratedArchSlotForCurrentAirfoil(i, scale_factor, current_chord_mm, slot_index);
    }
}

module CreateMode3GridVoid()
{
    wing_section_mm = wing_mm / wing_sections;
    translate([ wing_root_chord_mm * (wing_center_line_perc / 100), 0, 0 ]) union()
    {
        for (i = [0:wing_sections - 1])
        {
            current_z = (wing_mode == 1) ? wing_section_mm * i : f(i, wing_sections, wing_mm);
            next_z = (wing_mode == 1) ? wing_section_mm * (i + 1) : f(i + 1, wing_sections, wing_mm);
            current_chord_mm = (wing_mode == 1) ? ChordLengthAtIndex(i, wing_sections)
                                                : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm,
                                                                              current_z);
            next_chord_mm = (wing_mode == 1) ? ChordLengthAtIndex(i + 1, wing_sections)
                                             : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm,
                                                                           next_z);
            current_trailing_end_fraction = Mode3CenterlineTrailingEndFraction(Mode3AirfoilSliceForIndex(i),
                                                                               current_chord_mm);
            next_trailing_end_fraction = Mode3CenterlineTrailingEndFraction(Mode3AirfoilSliceForIndex(i + 1),
                                                                            next_chord_mm);

            for (j = [0:mode3_centerline_samples - 1])
            {
                hull()
                {
                    Mode3CenterlineSlicePoint(current_z, i, j, current_chord_mm, current_trailing_end_fraction);
                    Mode3CenterlineSlicePoint(current_z, i, j + 1, current_chord_mm, current_trailing_end_fraction);
                    Mode3CenterlineSlicePoint(next_z, i + 1, j, next_chord_mm, next_trailing_end_fraction);
                    Mode3CenterlineSlicePoint(next_z, i + 1, j + 1, next_chord_mm, next_trailing_end_fraction);
                }
            }
        }
    }
}

module CreateMode3LighteningVoids()
{
    wing_section_mm = wing_mm / wing_sections;
    translate([ wing_root_chord_mm * (wing_center_line_perc / 100), 0, 0 ]) union()
    {
        if (Mode3GeneratedArchSlotsEnabled())
        {
            for (slot_index = [0:mode3_arch_slot_count - 1])
            {
                for (i = [0:wing_sections - 1])
                {
                    current_z = (wing_mode == 1) ? wing_section_mm * i : f(i, wing_sections, wing_mm);
                    next_z = (wing_mode == 1) ? wing_section_mm * (i + 1) : f(i + 1, wing_sections, wing_mm);

                    hull()
                    {
                        Mode3GeneratedArchSlotSlice(current_z, i, slot_index);
                        Mode3GeneratedArchSlotSlice(next_z, i + 1, slot_index);
                    }
                }
            }
        }
        else
        {
            for (chord_fraction = mode3_lightening_chord_fractions)
            {
                if (Mode3HoleClearsSpar(chord_fraction, wing_root_chord_mm, 0))
                {
                    for (i = [0:wing_sections - 1])
                    {
                        current_z = (wing_mode == 1) ? wing_section_mm * i : f(i, wing_sections, wing_mm);
                        next_z = (wing_mode == 1) ? wing_section_mm * (i + 1) : f(i + 1, wing_sections, wing_mm);

                        hull()
                        {
                            Mode3LighteningSliceDisk(current_z, i, chord_fraction);
                            Mode3LighteningSliceDisk(next_z, i + 1, chord_fraction);
                        }
                    }
                }
            }
        }
    }
}

module RibThinZoneKeepoutBands(AFPoints, current_chord_mm, z_size)
{
    leading_end_fraction = RibThinZoneLeadingEndFraction(AFPoints, current_chord_mm);
    trailing_start_fraction = RibThinZoneTrailingStartFraction(AFPoints, current_chord_mm);
    leading_x_size = current_chord_mm * leading_end_fraction;
    trailing_x_size = current_chord_mm * (1 - trailing_start_fraction);
    y_size = wing_root_chord_mm * 2;

    if (leading_x_size > 0.001)
    {
        translate([ leading_x_size / 2, 0, 0 ]) cube([ leading_x_size, y_size, z_size ], center = true);
    }

    if (trailing_x_size > 0.001)
    {
        translate([ current_chord_mm * (trailing_start_fraction + 1) / 2, 0, 0 ])
            cube([ trailing_x_size, y_size, z_size ], center = true);
    }
}

module RibThinZoneKeepoutBandsForCurrentAirfoil(i, scale_factor, current_chord_mm, z_size)
{
    if (i > wing_sections * (tip_airfoil_change_perc / 100))
    {
        RibThinZoneKeepoutBands(scalePath(af_vec_path_tip, scale_factor), current_chord_mm, z_size);
    }
    else if (i > wing_sections * (center_airfoil_change_perc / 100))
    {
        RibThinZoneKeepoutBands(scalePath(af_vec_path_mid, scale_factor), current_chord_mm, z_size);
    }
    else
    {
        RibThinZoneKeepoutBands(scalePath(af_vec_path_root, scale_factor), current_chord_mm, z_size);
    }
}

module RibThinZoneWashoutKeepoutBands(i, scale_factor, current_chord_mm, z_size)
{
    washout_start_point = (wing_mode == 1) ? (wing_sections * (washout_start / 100))
                                           : WashoutStart(0, wing_sections, washout_start, wing_mm);
    washout_deg_frac = washout_deg / (wing_sections - washout_start_point);
    washout_deg_amount = (washout_start_point - i) * washout_deg_frac;
    rotate_point = current_chord_mm * (washout_pivot_perc / 100);

    translate([ rotate_point, 0, 0 ]) rotate(washout_deg_amount) translate([ -rotate_point, 0, 0 ])
        RibThinZoneKeepoutBandsForCurrentAirfoil(i, scale_factor, current_chord_mm, z_size);
}

module RibThinZoneSliceKeepoutBands(z_location, i, z_size)
{
    current_chord_mm = (wing_mode == 1) ? ChordLengthAtIndex(i, wing_sections)
                                        : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm, z_location);
    scale_factor = current_chord_mm / 100;

    translate([ 0, 0, z_location ]) translate([ -wing_center_line_perc / 100 * current_chord_mm, 0, 0 ])
        if (washout_deg > 0 && ((wing_mode > 1 && i > WashoutStart(0, wing_sections, washout_start, wing_mm)) ||
                                (wing_mode == 1 && i > (wing_sections * (washout_start / 100)))))
    {
        RibThinZoneWashoutKeepoutBands(i, scale_factor, current_chord_mm, z_size);
    }
    else
    {
        RibThinZoneKeepoutBandsForCurrentAirfoil(i, scale_factor, current_chord_mm, z_size);
    }
}

module CreateRibThinZoneKeepout()
{
    wing_section_mm = wing_mm / wing_sections;
    z_size = wing_section_mm + (max(rib_leading_thin_zone_blend_mm, rib_trailing_thin_zone_blend_mm) * 2);

    translate([ wing_root_chord_mm * (wing_center_line_perc / 100), 0, 0 ]) union()
    {
        for (i = [0:wing_sections])
        {
            z_location = (wing_mode == 1) ? wing_section_mm * i : f(i, wing_sections, wing_mm);
            RibThinZoneSliceKeepoutBands(z_location, i, z_size);
        }
    }
}

module GridWashoutSlice(i, scale_factor, current_chord_mm, LE)
{

    washout_start_point = (wing_mode == 1) ? (wing_sections * (washout_start / 100))
                                           : WashoutStart(0, wing_sections, washout_start, wing_mm);
    washout_deg_frac = washout_deg / (wing_sections - washout_start_point);
    washout_deg_amount = (washout_start_point - i) * washout_deg_frac;
    rotate_point = current_chord_mm * (washout_pivot_perc / 100);

    translate([ rotate_point, 0, 0 ]) rotate(washout_deg_amount) translate([ -rotate_point, 0, 0 ])
        GridESlice(i, scale_factor, LE);
}

module GridESlice(i, scale_factor, LE)
{

    if (i > wing_sections * (tip_airfoil_change_perc / 100))
    {
        if (LE)
        {
            CamberVoidLE(scalePath(af_vec_path_tip, scale_factor));
        }
        else
        {
            CamberVoidTE(scalePath(af_vec_path_tip, scale_factor));
        }
    }
    else if (i > wing_sections * (center_airfoil_change_perc / 100))
    {
        if (LE)
        {
            CamberVoidLE(scalePath(af_vec_path_mid, scale_factor));
        }
        else
        {
            CamberVoidTE(scalePath(af_vec_path_mid, scale_factor));
        }
    }
    else
    {
        if (LE)
        {
            CamberVoidLE(scalePath(af_vec_path_root, scale_factor));
        }
        else
        {
            CamberVoidTE(scalePath(af_vec_path_root, scale_factor));
        }
    }
}

module GridSlice(z_location, i, LE)
{
    current_chord_mm = (wing_mode == 1) ? ChordLengthAtIndex(i, wing_sections)
                                        : ChordLengthAtEllipsePosition((wing_mm + 0.1), wing_root_chord_mm, z_location);

    scale_factor = current_chord_mm / 100;
    translate([ 0, 0, z_location ]) translate([ -wing_center_line_perc / 100 * current_chord_mm, 0, 0 ])

        if (washout_deg > 0 && ((wing_mode > 1 && i > WashoutStart(0, wing_sections, washout_start, wing_mm)) ||
                                (wing_mode == 1 && i > (wing_sections * (washout_start / 100)))))
    {
        GridWashoutSlice(i, scale_factor, current_chord_mm, LE);
    }
    else
    {
        GridESlice(i, scale_factor, LE);
    }
}

module CreateGridVoid()
{
    wing_section_mm = wing_mm / wing_sections;
    if (wing_mode == 1)
    {
        translate([ wing_root_chord_mm * (wing_center_line_perc / 100), 0, 0 ]) union()
        {
            color("red") union()
            {
                for (i = [0:wing_sections])
                {
                    hull()
                    {
                        GridSlice(wing_section_mm * i, i, true);
                        GridSlice(wing_section_mm * (i + 1), i + 1, true);
                    }
                }
            }
            color("green") union()
            {
                for (i = [0:wing_sections])
                {
                    hull()
                    {
                        GridSlice(wing_section_mm * i, i, false);
                        GridSlice(wing_section_mm * (i + 1), i + 1, false);
                    }
                }
            }
        }
    }
    else
    {
        translate([ wing_root_chord_mm * (wing_center_line_perc / 100), 0, 0 ]) union()
        {
            color("red") union()
            {
                for (i = [0:wing_sections])
                {
                    pos = f(i, wing_sections, wing_mm);
                    npos = f((i + 1), wing_sections, wing_mm);
                    hull()
                    {
                        GridSlice(pos, i, true);
                        GridSlice(npos, (i + 1), true);
                    }
                }
            }
            color("blue") union()
            {
                for (i = [0:wing_sections])
                {
                    pos = f(i, wing_sections, wing_mm);
                    npos = f((i + 1), wing_sections, wing_mm);
                    hull()
                    {
                        GridSlice(pos, i, false);
                        GridSlice(npos, (i + 1), false);
                    }
                }
            }
        }
    }
}
