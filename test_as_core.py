import bz2
import gzip
import math
import os

from as_core import (
    build_country_topology,
    build_topology_from_caida,
    calculate_angle,
    calculate_radius,
    compute_bezier_curve,
    compute_customer_cones,
    infer_indonesia_region,
    infer_rir_and_longitude,
    load_caida_as_rel,
    main,
    parse_highlight_asns,
    render_as_core,
)


def _mock_cache(tmp_path, country="ID", asns=None):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(exist_ok=True)
    if asns is None:
        asns = [7713, 4761, 17451, 24203, 7597, 7717, 4796, 64302]
    cache_file = cache_dir / f"delegated_{country.upper()}.txt"
    cache_file.write_text("\n".join(str(a) for a in asns) + "\n", encoding="utf-8")
    return str(cache_dir)


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


def test_compute_customer_cones_and_cycles():
    customer_graph = {1: [2, 4], 2: [3], 3: [1]}
    cones = compute_customer_cones(customer_graph)
    assert cones[1] == 3
    assert cones[2] == 3
    assert cones[3] == 3


def test_load_caida_as_rel_plain_and_compressed(tmp_path):
    sample_content = """# CAIDA format sample
100|200|-1|bgp
100|300|-1|bgp
200|400|-1|bgp
300|400|0|bgp
"""
    txt_path = str(tmp_path / "sample.as-rel2.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(sample_content)

    bz2_path = str(tmp_path / "sample.as-rel2.txt.bz2")
    with bz2.open(bz2_path, "wt", encoding="utf-8") as f:
        f.write(sample_content)

    gz_path = str(tmp_path / "sample.as-rel2.txt.gz")
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.write(sample_content)

    for path in (txt_path, bz2_path, gz_path):
        customer_graph, edges = load_caida_as_rel(path)
        assert len(edges) == 4
        assert customer_graph[100] == [200, 300]


def test_build_topology_from_caida(tmp_path):
    sample_content = """# CAIDA sample
3356|174|-1|bgp
3356|1299|0|bgp
174|15169|-1|bgp
"""
    file_path = str(tmp_path / "caida.as-rel2.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(sample_content)

    nodes, edges = build_topology_from_caida(file_path, top_n=10)
    assert 3356 in nodes
    assert 174 in nodes
    assert nodes[3356].cone_size == 2
    assert len(edges) == 3


def test_infer_indonesia_region_and_determinism():
    # Telkom Indonesia
    name, region, lon = infer_indonesia_region(7713)
    assert "Telkom" in name
    assert region == "Java"
    assert math.isclose(lon, 106.8, abs_tol=0.1)

    # OpenIXP
    name, region, lon = infer_indonesia_region(7717)
    assert "OpenIXP" in name
    assert region == "Java"
    assert math.isclose(lon, 106.8, abs_tol=0.1)

    # Batam Bintan Telko
    name, region, _ = infer_indonesia_region(131759)
    assert region == "Sumatra"

    # Deterministic unknown ASN inference
    assert infer_indonesia_region(139999) == infer_indonesia_region(139999)
    assert infer_rir_and_longitude(50000) == infer_rir_and_longitude(50000)


def test_build_country_topology(tmp_path):
    cache_dir = _mock_cache(tmp_path, "ID")
    nodes, edges = build_country_topology(
        file_path=None, country_code="ID", top_n=50, cache_dir=cache_dir
    )
    assert 7713 in nodes  # Telkom Indonesia
    assert 4761 in nodes  # Indosat
    assert 24203 in nodes  # XL Axiata
    assert 7597 in nodes  # APJII / IIX
    assert 7717 in nodes  # OpenIXP
    assert 4796 in nodes  # ITB (Bandung)
    assert 64302 in nodes  # IDREN
    assert len(nodes) > 0
    assert len(edges) > 0
    assert nodes[7713].country == "ID"
    assert "OpenIXP" in nodes[7717].name
    assert "ITB" in nodes[4796].name
    assert "IDREN" in nodes[64302].name

    # Non-ID country simulation fallback
    us_cache = _mock_cache(tmp_path, "US", asns=[3356, 174, 701, 15169, 13335])
    us_nodes, us_edges = build_country_topology(
        file_path=None, country_code="US", top_n=10, cache_dir=us_cache
    )
    assert len(us_nodes) == 5
    assert len(us_edges) > 0


def test_parse_highlight_asns():
    assert parse_highlight_asns("AS7713, as4761, 24203", "GLOBAL") == [7713, 4761, 24203]
    assert parse_highlight_asns("invalid", "GLOBAL") is None
    assert parse_highlight_asns(None, "GLOBAL") == [7713]
    assert 7713 in parse_highlight_asns(None, "ID")


def test_render_as_core_country_integration(tmp_path):
    cache_dir = _mock_cache(tmp_path, "ID")
    nodes, edges = build_country_topology(
        file_path=None, country_code="ID", top_n=30, cache_dir=cache_dir
    )
    out_file = str(tmp_path / "test_id_core.png")

    highlight = [7713, 4761, 24203, 7597, 7717, 4796, 64302]
    fig = render_as_core(
        nodes,
        edges,
        output_path=out_file,
        dpi=100,
        country="ID",
        title="Indonesia Test",
        highlight_asns=highlight,
    )
    assert fig is not None
    assert os.path.exists(out_file)
    assert os.path.getsize(out_file) > 10000


def test_cli_main(tmp_path):
    out_file = str(tmp_path / "cli_out.png")
    sample_file = str(tmp_path / "sample.as-rel2.txt")
    with open(sample_file, "w", encoding="utf-8") as f:
        f.write("3356|174|-1|bgp\n174|15169|-1|bgp\n")

    main(["-i", sample_file, "-c", "GLOBAL", "-n", "10", "-s", "AS3356,174", "-o", out_file])
    assert os.path.exists(out_file)
