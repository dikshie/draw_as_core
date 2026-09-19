import os
import math
import pytest
import numpy as np
from as_core import (
    ASNode,
    calculate_radius,
    calculate_angle,
    polar_to_cartesian,
    compute_bezier_curve,
    prepare_graph_coordinates,
    generate_sample_2020_topology,
    render_as_core
)


def test_calculate_radius_boundaries():
    max_cone = 40000
    
    # Core AS (cone == max_cone) -> r = 0.0
    r_core = calculate_radius(max_cone, max_cone)
    assert math.isclose(r_core, 0.0, abs_tol=1e-6)
    
    # Stub AS (cone == 0) -> r = 1.0
    r_stub = calculate_radius(0, max_cone)
    assert math.isclose(r_stub, 1.0, abs_tol=1e-6)
    
    # Out of bounds / invalid inputs
    assert calculate_radius(-10, max_cone) == 1.0
    assert calculate_radius(10, 0) == 1.0


def test_calculate_radius_monotonicity():
    max_cone = 50000
    cones = [0, 10, 100, 1000, 5000, 20000, 50000]
    radii = [calculate_radius(c, max_cone) for c in cones]
    
    # As customer cone size increases, radius must strictly decrease
    for i in range(len(radii) - 1):
        assert radii[i] > radii[i + 1]


def test_calculate_angle_and_polar_conversion():
    # Longitude 0 -> theta = 0 rad -> (1, 0) at r=1
    theta_0 = calculate_angle(0.0)
    assert math.isclose(theta_0, 0.0, abs_tol=1e-6)
    x, y = polar_to_cartesian(1.0, theta_0)
    assert math.isclose(x, 1.0, abs_tol=1e-6)
    assert math.isclose(y, 0.0, abs_tol=1e-6)

    # Longitude 90 -> theta = pi/2 rad -> (0, 1) at r=1
    theta_90 = calculate_angle(90.0)
    assert math.isclose(theta_90, math.pi / 2, abs_tol=1e-6)
    x, y = polar_to_cartesian(1.0, theta_90)
    assert math.isclose(x, 0.0, abs_tol=1e-6)
    assert math.isclose(y, 1.0, abs_tol=1e-6)

    # Radius = 0 -> (0, 0) regardless of theta
    x_center, y_center = polar_to_cartesian(0.0, theta_90)
    assert math.isclose(x_center, 0.0, abs_tol=1e-6)
    assert math.isclose(y_center, 0.0, abs_tol=1e-6)


def test_compute_bezier_curve():
    p1 = (1.0, 0.0)
    p2 = (0.0, 1.0)
    num_pts = 20
    bx, by = compute_bezier_curve(p1, p2, bend_factor=0.3, num_points=num_pts)
    
    assert len(bx) == num_pts
    assert len(by) == num_pts
    
    # Start point must match p1
    assert math.isclose(bx[0], p1[0], abs_tol=1e-5)
    assert math.isclose(by[0], p1[1], abs_tol=1e-5)
    
    # End point must match p2
    assert math.isclose(bx[-1], p2[0], abs_tol=1e-5)
    assert math.isclose(by[-1], p2[1], abs_tol=1e-5)
    
    # Midpoint of straight chord is (0.5, 0.5) distance = ~0.707
    # Midpoint of curved spline should bend closer to the center (0,0)
    mid_idx = num_pts // 2
    chord_mid_dist = math.sqrt(0.5**2 + 0.5**2)
    curve_mid_dist = math.sqrt(bx[mid_idx]**2 + by[mid_idx]**2)
    assert curve_mid_dist < chord_mid_dist


def test_prepare_graph_coordinates():
    nodes = {
        1: ASNode(asn=1, name="Tier1", cone_size=10000, longitude=0.0, rir="ARIN"),
        2: ASNode(asn=2, name="Stub", cone_size=0, longitude=90.0, rir="RIPE")
    }
    
    prepare_graph_coordinates(nodes)
    
    assert math.isclose(nodes[1].r, 0.0, abs_tol=1e-6)
    assert math.isclose(nodes[2].r, 1.0, abs_tol=1e-6)
    assert math.isclose(nodes[2].x, 0.0, abs_tol=1e-6)
    assert math.isclose(nodes[2].y, 1.0, abs_tol=1e-6)


def test_render_as_core_integration(tmp_path):
    nodes, edges = generate_sample_2020_topology(num_stubs=50)
    out_file = str(tmp_path / "test_core.png")
    
    fig = render_as_core(nodes, edges, output_path=out_file, dpi=100)
    assert fig is not None
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 10000  # Non-trivial image generated
