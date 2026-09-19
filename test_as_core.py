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
    compute_customer_cones,
    load_caida_as_rel,
    infer_rir_and_longitude,
    prepare_graph_coordinates,
    build_topology_from_caida,
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
    
    mid_idx = num_pts // 2
    chord_mid_dist = math.sqrt(0.5**2 + 0.5**2)
    curve_mid_dist = math.sqrt(bx[mid_idx]**2 + by[mid_idx]**2)
    assert curve_mid_dist < chord_mid_dist


def test_compute_customer_cones():
    # Tree: 1 -> 2 -> 3
    #            1 -> 4
    # Cone of 1 = {2, 3, 4} -> size 3
    # Cone of 2 = {3} -> size 1
    # Cone of 3 = 0, Cone of 4 = 0
    customer_graph = {
        1: [2, 4],
        2: [3]
    }
    cones = compute_customer_cones(customer_graph)
    assert cones[1] == 3
    assert cones[2] == 1


def test_load_caida_as_rel(tmp_path):
    sample_content = """# CAIDA format sample
# provider|customer|-1|source
100|200|-1|bgp
100|300|-1|bgp
200|400|-1|bgp
300|400|0|bgp
"""
    file_path = str(tmp_path / "sample.as-rel2.txt")
    with open(file_path, "w") as f:
        f.write(sample_content)

    customer_graph, edges = load_caida_as_rel(file_path)
    assert len(edges) == 4
    assert customer_graph[100] == [200, 300]
    assert customer_graph[200] == [400]
    
    cones = compute_customer_cones(customer_graph)
    assert cones[100] == 3  # 200, 300, 400


def test_infer_rir_and_longitude():
    # Well-known ASN
    name, rir, lon = infer_rir_and_longitude(3356)
    assert "Level 3" in name or "Lumen" in name
    assert rir == "ARIN"
    assert lon == -105.0

    # APNIC range
    _, apnic_rir, apnic_lon = infer_rir_and_longitude(4609)
    assert apnic_rir == "APNIC"

    # RIPE range
    _, ripe_rir, ripe_lon = infer_rir_and_longitude(32000)
    assert ripe_rir == "RIPE"


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
    assert os.path.getsize(out_file) > 10000
