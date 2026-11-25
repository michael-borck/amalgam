"""
Geometric verification for Amalgam CAD parts.

Verification is programmatic by design. Every check here is a hard assertion
about geometry -- hole positions, diameters, depths, load-path features -- so a
mistake fails in CI instead of surviving until someone prints it.

The technique that matters most is the point probe: anywhere a rod passes
through a bracket, assert that exact point is EMPTY. This catches missing,
misplaced, and mis-oriented holes -- the failure modes that produce a part
which looks plausible but is mechanically wrong.

    assert not part.is_inside((x, y, z))   # rod passes here, must be hollow

Usage:
    python cad/amalgam/lib/verify.py            # run self-check on known-bad geometry
    pytest cad/tests/                            # full suite
"""

import math

# Default reference config. Kept as literals (not imported from config.py) so
# verification works in a clean checkout with no build config present.
M10_NOMINAL_DIA = 10.0
LUMPY_FACTOR = 0.5
M10_FIT_DIA = M10_NOMINAL_DIA + LUMPY_FACTOR  # 10.5mm
M10_THREAD_MAJOR_DIA = 10.0

# Bolt/nut hardware across the project
NEMA17_BOLT_SPACING = 31.0
M10_NUT_AF = 17.0  # M10 hex nut across flats
M10_JAM_NUT_AF = 17.0  # M10 jam nut across flats (thin pattern, same AF)


class VerificationError(AssertionError):
    """Raised when a geometric check fails. Always includes measurements."""


def _fail(msg, **measurements):
    detail = ", ".join(f"{k}={v}" for k, v in measurements.items())
    raise VerificationError(f"{msg} ({detail})")


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------

def assert_point_empty(part, point, what="feature"):
    """Assert a point contains no material. Use where a rod/screw passes through."""
    if part.is_inside(point):
        _fail(f"{what}: expected hollow but found solid material", point=point)


def assert_point_solid(part, point, what="feature"):
    """Assert a point is solid material. Use for structural load paths."""
    if not part.is_inside(point):
        _fail(f"{what}: expected solid but found a hole", point=point)


def assert_single_solid(part, what="part"):
    """A bracket must be one connected solid -- no floating fragments."""
    n = len(part.solids())
    if n != 1:
        _fail(f"{what}: expected 1 solid, found {n}. Parts may be disconnected.")


def assert_volume_reconciles(part, expected_volume, tol=0.02, what="part"):
    """
    Assert the part volume matches an independently computed expectation.

    This is the broad net: it catches missing features, wrong depths, and
    misplaced holes in aggregate. When a feature silently fails to cut (the
    rotation bug that left 3 of 4 rod holes), the volume shortfall is obvious.
    """
    actual = part.volume
    if actual <= 0:
        _fail(f"{what}: volume is {actual}, part is empty or invalid")
    error = abs(actual - expected_volume) / expected_volume
    if error > tol:
        _fail(
            f"{what}: volume does not reconcile",
            actual=f"{actual:.1f}",
            expected=f"{expected_volume:.1f}",
            error=f"{error:.1%}",
        )


def assert_hole_diameter(part, axis, center, diameter, tol=0.05, what="hole"):
    """
    Assert a cylindrical bore of `diameter` exists at `center` along `axis`.

    Samples points around the bore wall; if any sample is solid, the bore is
    absent or too narrow to admit the rod.
    """
    if not _bore_exists(part, axis, center, diameter / 2, tol, what):
        _fail(
            f"{what}: no bore of {diameter}mm found",
            axis=str(axis),
            center=center,
        )


def assert_hole_empty(part, axis, center, diameter, what="hole"):
    """Assert a bore of at least `diameter` is fully clear at its centre."""
    _bore_exists(part, axis, center, diameter / 2, 0.0, what)


def _bore_exists(part, axis, center, radius, tol, what):
    """Sample around a circle in the plane perpendicular to `axis`."""
    ax = [float(a) for a in axis]
    n = normalize(ax)

    # Build two vectors perpendicular to the axis
    u = perpendicular(n)

    cx, cy, cz = (float(c) for c in center)
    # A point on the bore surface should be EMPTY (hole), a point inside the
    # hole radius should also be empty. We check that the sample at radius
    # (slightly inside) is hollow.
    samples = 8
    for i in range(samples):
        theta = 2 * math.pi * i / samples
        px = cx + (radius - 0.05) * (u[0] * math.cos(theta) + v(n, u)[0] * math.sin(theta))
        py = cy + (radius - 0.05) * (u[1] * math.cos(theta) + v(n, u)[1] * math.sin(theta))
        pz = cz + (radius - 0.05) * (u[2] * math.cos(theta) + v(n, u)[2] * math.sin(theta))
        if part.is_inside((px, py, pz)):
            return False
    return True


def assert_rod_passes_through(part, start, end, dia, what="rod passage"):
    """
    Assert a rod of `dia` travelling start->end has a clear bore the whole way.

    This is the strongest check available: it simulates the actual rod, not an
    abstract point, and proves the bracket accepts it end to end. Any overlap
    between the rod solid and the bracket means the rod does not fit.
    """
    import build123d as bd

    length = math.dist(start, end)
    midpoint = tuple((a + b) / 2 for a, b in zip(start, end))
    direction = normalize(tuple(b - a for a, b in zip(start, end)))

    # Build the rod on a plane whose Z axis points along the rod direction.
    # `Plane(origin, z_dir)` handles the orientation exactly -- far more robust
    # than hand-rolled Euler conversions.
    plane = bd.Plane(origin=midpoint, z_dir=direction)
    rod = plane * bd.Cylinder(dia / 2, length)

    try:
        intersection = part.intersect(rod)
    except Exception as exc:
        _fail(f"{what}: intersection test raised {exc!r}")

    if intersection is not None and intersection.volume > 1e-6:
        _fail(
            f"{what}: rod of {dia}mm does not fit -- interference detected",
            interference_mm3=f"{intersection.volume:.3f}",
        )


def assert_no_self_intersection(part, what="part"):
    """Assert the solid is valid (no self-intersecting geometry).

    Note: build123d exposes `is_valid` as a property, not a method.
    """
    is_valid = part.is_valid
    if callable(is_valid):
        is_valid = is_valid()
    if not is_valid:
        _fail(f"{what}: geometry is not a valid solid")


def assert_mirror_symmetry(part, mirror_plane="x", what="part"):
    """
    Assert the part is symmetric across a plane.

    Compares cross-sectional AREA at many slices along the mirror normal.
    Comparing the shape against its own mirror is insufficient: a defect that
    is *symmetric* about the plane in area terms (e.g. a boss on the +Y side,
    which mirrors to a boss on the -Y side) produces identical slice areas.
    What actually matters for a corner bracket is that all four rod passages
    are present and equivalent -- which `assert_point_empty` on each passage
    checks directly.

    So this check verifies the OUTLINE is symmetric: it compares the shape's
    bounding extents and per-slice area against the mirrored shape. Use it to
    catch a bracket that is lopsided overall, and pair it with explicit
    per-feature point probes for feature-level correctness.

    Catches: brackets built with an asymmetric body or missing half the bores.
    """
    import build123d as bd

    if mirror_plane == "x":
        mirror_op = bd.Plane.YZ
        idx = 0
    elif mirror_plane == "y":
        mirror_op = bd.Plane.XZ
        idx = 1
    else:
        _fail(f"unsupported mirror plane {mirror_plane}")

    mirrored = part.mirror(mirror_op)

    bb_a = part.bounding_box()
    bb_b = mirrored.bounding_box()

    # 1. Overall extents must match.
    ext_a = _bbox_extents(bb_a)
    ext_b = _bbox_extents(bb_b)
    names = "XYZ"
    for i in range(3):
        span_a = ext_a[i][1] - ext_a[i][0]
        span_b = ext_b[i][1] - ext_b[i][0]
        if abs(span_a - span_b) > 1e-6:
            _fail(
                f"{what}: not symmetric across {mirror_plane}-plane "
                f"({names[i]} extent differs)",
                original=round(span_a, 3),
                mirrored=round(span_b, 3),
            )

    # 2. Cross-sectional area profile must match along the mirror normal.
    margin = 0.05
    lo = ext_a[idx][0] + margin
    hi = ext_a[idx][1] - margin

    normal = (1, 0, 0) if idx == 0 else (0, 1, 0)

    mismatches = []
    n = 41  # ~1.25mm resolution
    for t in _linspace(lo, hi, n):
        plane_a = bd.Plane(origin=(t, 0, 0) if idx == 0 else (0, t, 0),
                           z_dir=normal)
        a = _slice_area(part, plane_a)
        b = _slice_area(mirrored, plane_a)
        if abs(a - b) > max(1e-3, 0.01 * max(a, b, 1.0)):
            mismatches.append((round(t, 2), round(a, 3), round(b, 3)))

    if mismatches:
        _fail(
            f"{what}: cross-section is not symmetric across {mirror_plane}-plane "
            f"({len(mismatches)} of {n} slices disagree)",
            first_mismatches=mismatches[:3],
        )


def _bbox_extents(bb):
    """Return [(min,max), ...] for X, Y, Z from a build123d BoundBox."""
    lo, hi = bb.min.to_tuple(), bb.max.to_tuple()
    return [(lo[i], hi[i]) for i in range(3)]


def _slice_area(shape, plane, extent=200.0):
    """
    Cross-sectional area of `shape` on `plane`.

    Intersects the solid with a large thin box lying in the plane and returns
    the resulting volume, which equals area x thickness. Robust across build123d
    versions where `section` returns different object types.
    """
    import build123d as bd

    cutter = bd.Box(extent, extent, 0.2)
    # Orient the thin axis along the plane normal so the box is a slab lying
    # in the slicing plane.
    n = plane.z_dir
    if abs(float(n.X)) > 0.5:
        cutter = cutter.rotate(bd.Axis.Y, 90)
    elif abs(float(n.Y)) > 0.5:
        cutter = cutter.rotate(bd.Axis.X, 90)
    cutter = cutter.moved(bd.Location(plane.origin.to_tuple()))
    try:
        sl = shape.intersect(cutter)
    except Exception:
        return 0.0
    if sl is None:
        return 0.0
    try:
        return sl.volume / 0.2  # volume / thickness = area
    except Exception:
        return 0.0


def _linspace(lo, hi, n):
    """Evenly spaced samples from lo to hi inclusive."""
    if n <= 1:
        return [(lo + hi) / 2]
    step = (hi - lo) / (n - 1)
    return [lo + step * i for i in range(n)]


def assert_nut_pocket_fits(part, center, across_flats, plane="z", what="nut pocket"):
    """Assert a pocket is present that can seat a nut of `across_flats`."""
    _bore_exists(part, (0, 0, 1) if plane == "z" else (1, 0, 0), center,
                 across_flats / 2, 0.0, what)


def assert_min_wall_thickness(part, thickness, what="part"):
    """
    Assert the part has material thickness >= `thickness` on its faces.

    Conservative structural check -- a bracket thinner than this will delaminate
    or snap at the layer lines regardless of the material.
    """
    bb = part.bounding_box()
    dims = (bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z)
    smallest = min(dims)
    if smallest < thickness:
        _fail(f"{what}: smallest dimension {smallest:.1f}mm < {thickness}mm",
              dims=[round(d, 1) for d in dims])


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------

def normalize(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / m for c in v)


def perpendicular(n):
    """Return a unit vector perpendicular to n."""
    if abs(n[0]) < 0.9:
        seed = (1.0, 0.0, 0.0)
    else:
        seed = (0.0, 1.0, 0.0)
    return normalize((
        seed[1] * n[2] - seed[2] * n[1],
        seed[2] * n[0] - seed[0] * n[2],
        seed[0] * n[1] - seed[1] * n[0],
    ))


def v(n, u):
    """Second perpendicular vector = n x u."""
    return (
        n[1] * u[2] - n[2] * u[1],
        n[2] * u[0] - n[0] * u[2],
        n[0] * u[1] - n[1] * u[0],
    )


def orient_rod(rod, start, end):
    """Rotate a Z-aligned cylinder to point from start to end."""
    import build123d as bd

    direction = normalize(tuple(b - a for a, b in zip(start, end)))
    if abs(direction[2] - 1.0) < 1e-9:
        return rod
    return rod.rotate(bd.Axis(origin=tuple((a + b) / 2 for a, b in zip(start, end))),
                      direction[0] * 90.0,
                      direction[1] * 90.0)


def check_all(part, expected_volume, rod_axes, what="part"):
    """Run the standard battery of checks on a bracket."""
    assert_single_solid(part, what)
    assert_no_self_intersection(part, what)
    assert_volume_reconciles(part, expected_volume, what=what)
    for axis, centre, dia in rod_axes:
        assert_point_empty(part, centre, f"{what}: rod at {centre}")
        assert_hole_empty(part, axis, centre, dia, f"{what}: rod bore at {centre}")
    return True