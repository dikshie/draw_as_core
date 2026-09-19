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
    infer_indonesia_region,
    fetch_country_asns,
    build_country_topology,
    prepare_graph_coordinates,
    generate_sample_2020_topology,
    render_as_core
)


def test_calculate_radius_boundaries():
    max_cone = 40000
    r_core = calculate_radius(max_cone, max_cone)
    assert math.isclose(r_core, 0.0, abs_tol=1e-6)
    
    r_stub = calculate_radius(0, max_cone)
    assert math.isclose(r_stub, 1.0, abs_tol=1e-6)
    
    assert calculate_radius(-10, max_cone) == 1.0
    assert calculate_radius(10, 0) == 1.0


def test_calculate_radius_monotonicity():
    max_cone = 50000
    cones = [0, 10, 100, 1000, 5000, 20000, 50000]
    radii = [calculate_radius(c, max_cone) for c in cones]
    
    for i in range(len(radii) - 1):
        assert radii[i] > radii[i + 1]


def test_calculate_angle_global_and_country():
    # Global longitude 0 -> 0 rad
    theta_0 = calculate_angle(0.0, country="GLOBAL")
    assert math.isclose(theta_0, 0.0, abs_tol=1e-6)
    
    # Indonesia: 95.0 E should map to -pi/2 (top start)
    theta_id_min = calculate_angle(95.0, country="ID")
    assert math.isclose(theta_id_min, -math.pi / 2, abs_tol=1e-6)
    
    # Indonesia: 141.0 E should map to 3pi/2 (full rotation)
    theta_id_max = calculate_angle(141.0, country="ID")
    assert math.isclose(theta_id_max, 3 * math.pi / 2, abs_tol=1e-6)


def test_compute_bezier_curve():
    p1 = (1.0, 0.0)
    p2 = (0.0, 1.0)
    num_pts = 20
    bx, by = compute_bezier_curve(p1, p2, bend_factor=0.3, num_points=num_pts)
    
    assert len(bx) == num_pts
    assert len(by) == num_pts
    assert math.isclose(bx[0], p1[0], abs_tol=1e-5)
    assert math.isclose(by[0], p1[1], abs_tol=1e-5)
    assert math.isclose(bx[-1], p2[0], abs_tol=1e-5)
    assert math.isclose(by[-1], p2[1], abs_tol=1e-5)


def test_compute_customer_cones():
    customer_graph = {
        1: [2, 4],
        2: [3]
    }
    cones = compute_customer_cones(customer_graph)
    assert cones[1] == 3
    assert cones[2] == 1


def test_load_caida_as_rel(tmp_path):
    sample_content = """# CAIDA format sample
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


def test_infer_indonesia_region():
    # Telkom Indonesia
    name, region, lon = infer_indonesia_region(7713)
    assert "Telkom" in name
    assert region == "Java"
    assert math.isclose(lon, 106.8, abs_tol=0.1)

    # Batam Bintan Telko
    name, region, _ = infer_indonesia_region(131759)
    assert region == "Sumatra"


def test_build_country_topology():
    nodes, edges = build_country_topology(file_path=None, country_code="ID", top_n=50)
    assert 7713 in nodes   # Telkom Indonesia
    assert 4761 in nodes   # Indosat
    assert 24203 in nodes  # XL Axiata
    assert 7597 in nodes   # APJII / IIX
    assert 4796 in nodes   # ITB (Bandung)
    assert len(nodes) > 0
    assert len(edges) > 0
    assert nodes[7713].country == "ID"
    assert "ITB" in nodes[4796].name


def test_render_as_core_country_integration(tmp_path):
    nodes, edges = build_country_topology(file_path=None, country_code="ID", top_n=30)
    out_file = str(tmp_path / "test_id_core.png")
    
    # Highlight specific ASes including ITB, Indosat, XL, APJII
    highlight = [7713, 4761, 24203, 7597, 4796]
    fig = render_as_core(
        nodes, edges, output_path=out_file, dpi=100, country="ID",
        title="Indonesia Test", highlight_asns=highlight
    )
    assert fig is not None
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 10000
