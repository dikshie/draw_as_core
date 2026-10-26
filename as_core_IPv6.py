"""
CAIDA-Style IPv6 AS Core Visualizer.

Implements the polar coordinate layout algorithm used by CAIDA to visualize
the macroscopic IPv6 Internet topology and AS Core.
Supports:
1. Global IPv6 AS Core topology visualization.
2. Country-specific IPv6 AS Core filtering and rendering (e.g. Indonesia - ID, US, JP, DE, SG).
3. Automatic RIR delegation fetching and offline fallback databases.
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np

from as_core import (
    ID_SECTOR_PALETTE,
    INDONESIA_WELL_KNOWN,
    RIR_PALETTE,
    WELL_KNOWN_ASES,
    ASNode,
    build_topology_from_caida,
    calculate_angle,
    calculate_radius,
    compute_bezier_curve,
    compute_customer_cones,
    fetch_country_asns,
    infer_indonesia_region,
    infer_rir_and_longitude,
    iter_file_lines,
    load_caida_as_rel,
    parse_highlight_asns,
    polar_to_cartesian,
    prepare_graph_coordinates,
)
from as_core import (
    build_country_topology as _build_country_topology,
)
from as_core import (
    render_as_core as _render_as_core,
)

__all__ = [
    "ASNode",
    "ID_SECTOR_PALETTE",
    "INDONESIA_WELL_KNOWN",
    "RIR_PALETTE",
    "WELL_KNOWN_ASES",
    "build_country_topology",
    "build_topology_from_caida",
    "calculate_angle",
    "calculate_radius",
    "compute_bezier_curve",
    "compute_customer_cones",
    "fetch_country_asns",
    "generate_sample_2020_topology",
    "generate_sample_ipv6_topology",
    "infer_indonesia_region",
    "infer_rir_and_longitude",
    "iter_file_lines",
    "load_caida_as_rel",
    "parse_highlight_asns",
    "polar_to_cartesian",
    "prepare_graph_coordinates",
    "render_as_core",
]

IPV6_SUBTITLE = r"$\mathrm{Radial\ position:}\ r = 1 - \frac{\log(\mathrm{IPv6\ CustomerCone} + 1)}{\log(\mathrm{MaxIPv6Cone} + 1)} \quad\vert\quad \mathrm{Angular\ position:}\ \theta = \mathrm{Longitude}$"


def generate_sample_ipv6_topology(
    num_stubs: int = 350,
) -> tuple[dict[int, ASNode], list[tuple[int, int]]]:
    """Generates a realistic representative global IPv6 topology."""
    nodes: dict[int, ASNode] = {}

    # In IPv6, Hurricane Electric (AS6939) is the dominant #1 backbone by customer cone and peering reach
    ipv6_cone_map = {
        6939: 56000,  # Hurricane Electric (Top IPv6 Backbone)
        3356: 48000,  # Lumen / Level 3
        1299: 46000,  # Arelion / Telia
        2914: 42000,  # NTT Comms
        174: 40000,  # Cogent
        3257: 36000,  # GTT Comms
        6453: 34000,  # Tata Comms
        5511: 31000,  # Orange
        6762: 29000,  # TI Sparkle
        6461: 27000,  # Zayo
        15169: 25000,  # Google
        13335: 24000,  # Cloudflare
        16509: 22000,  # Amazon AWS
        8075: 21000,  # Microsoft
        20940: 20000,  # Akamai
    }

    for asn, (name, rir, lon) in WELL_KNOWN_ASES.items():
        cone = ipv6_cone_map.get(asn, max(18000 - len(nodes) * 800, 500))
        nodes[asn] = ASNode(asn, name, cone, lon, rir)

    edges: list[tuple[int, int]] = [
        (6939, 3356),
        (6939, 1299),
        (6939, 2914),
        (6939, 174),
        (6939, 6453),
        (6939, 3257),
        (3356, 174),
        (3356, 1299),
        (3356, 2914),
        (3356, 6453),
        (3356, 3257),
        (174, 1299),
        (174, 2914),
        (174, 6453),
        (174, 3257),
        (1299, 2914),
        (1299, 6762),
        (1299, 1273),
        (2914, 6453),
        (2914, 6762),
        (6453, 3257),
        (6762, 1273),
        (15169, 6939),
        (15169, 3356),
        (15169, 1299),
        (15169, 2914),
        (15169, 174),
        (13335, 6939),
        (13335, 174),
        (13335, 3356),
        (13335, 1299),
        (16509, 6939),
        (16509, 3356),
        (16509, 1299),
        (16509, 2914),
        (8075, 6939),
        (8075, 3356),
        (8075, 1299),
        (8075, 174),
        (20940, 6939),
        (20940, 3356),
        (20940, 174),
        (27699, 6939),
        (27699, 3356),
        (27699, 174),
        (27699, 1299),
        (2609, 6939),
        (2609, 3356),
        (2609, 27699),
        (37100, 6939),
        (37100, 1299),
        (37100, 6453),
        (37100, 3356),
        (36903, 6939),
        (36903, 1299),
        (36903, 37100),
    ]

    rng = np.random.default_rng(42)
    tier1_keys = [6939, 3356, 174, 1299, 2914, 6453, 3257]
    for i in range(1000, 1000 + num_stubs):
        name, rir, lon = infer_rir_and_longitude(i)
        cone = int(rng.exponential(scale=25))
        nodes[i] = ASNode(i, name, cone, lon, rir)
        num_upstreams = int(rng.choice([1, 2, 3], p=[0.7, 0.22, 0.08]))
        upstreams = rng.choice(tier1_keys, size=num_upstreams, replace=False)
        for up in upstreams:
            edges.append((i, int(up)))

    return nodes, edges


generate_sample_2020_topology = generate_sample_ipv6_topology


def build_country_topology(
    file_path: str | None,
    country_code: str = "ID",
    top_n: int = 600,
    highlight_asns: list[int] | None = None,
    cache_dir: str = "data",
) -> tuple[dict[int, ASNode], list[tuple[int, int]]]:
    """
    Builds a country-specific IPv6 AS Core topology from CAIDA dataset or local simulation.
    """
    return _build_country_topology(
        file_path=file_path,
        country_code=country_code,
        top_n=top_n,
        highlight_asns=highlight_asns,
        ip_version=6,
        cache_dir=cache_dir,
    )


def render_as_core(
    nodes: dict[int, ASNode],
    edges: list[tuple[int, int]],
    output_path: str = "as_core_ipv6.png",
    dpi: int = 300,
    title: str = "IPv6 AS Core Visualization",
    country: str = "GLOBAL",
    highlight_asns: list[int] | None = None,
) -> plt.Figure:
    """Renders the polar IPv6 AS Core map replicating CAIDA's aesthetic."""
    return _render_as_core(
        nodes=nodes,
        edges=edges,
        output_path=output_path,
        dpi=dpi,
        title=title,
        country=country,
        highlight_asns=highlight_asns,
        subtitle=IPV6_SUBTITLE,
    )


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="CAIDA IPv6 AS Core Visualizer (Global & Country-Level)"
    )
    parser.add_argument(
        "-i",
        "--input",
        help="Path to CAIDA IPv6 *.as-rel2.txt or *.as-rel2.txt.bz2 file",
        default=None,
    )
    parser.add_argument(
        "-c",
        "--country",
        help="2-letter ISO Country Code (e.g. ID, US, JP, DE, SG) or 'GLOBAL'",
        default=None,
    )
    parser.add_argument(
        "-s",
        "--highlight",
        help="Comma-separated list of ASNs to highlight (e.g. 4796,4761,24203,7597,7717,64302)",
        default=None,
    )
    parser.add_argument(
        "-n",
        "--top",
        help="Top N ASes to visualize by IPv6 customer cone",
        type=int,
        default=700,
    )
    parser.add_argument("-o", "--output", help="Output PNG path", default=None)
    parser.add_argument("-t", "--title", help="Plot title", default=None)
    args = parser.parse_args(argv)

    # Interactive prompt if user didn't pass country via CLI and is in an interactive shell
    country = args.country
    if country is None:
        try:
            user_input = input(
                "Enter Country Code (e.g. ID for Indonesia, or press Enter for Global): "
            ).strip()
            country = user_input.upper() if user_input else "GLOBAL"
        except (EOFError, KeyboardInterrupt):
            country = "GLOBAL"
    else:
        country = country.upper()

    caida_v6_candidates = [
        "20260901.as-rel2-v6.txt",
        "20260901.as-rel2.v6.txt",
        "20260901.as-rel2-v6.txt.bz2",
    ]
    if args.input is None:
        for candidate in caida_v6_candidates:
            if os.path.exists(candidate):
                args.input = candidate
                break

    output_filename = args.output
    if output_filename is None:
        output_filename = (
            f"as_core_ipv6_{country.lower()}.png"
            if country != "GLOBAL"
            else "as_core_ipv6_global.png"
        )

    plot_title = args.title
    if plot_title is None:
        plot_title = (
            f"{country} IPv6 AS Core Topology"
            if country != "GLOBAL"
            else "CAIDA IPv6 AS Core Topology"
        )

    highlight_asns = parse_highlight_asns(args.highlight, country)

    if country != "GLOBAL":
        nodes, edges = build_country_topology(
            args.input,
            country_code=country,
            top_n=args.top,
            highlight_asns=highlight_asns,
        )
    else:
        if args.input and os.path.exists(args.input):
            nodes, edges = build_topology_from_caida(args.input, top_n=args.top)
        else:
            nodes, edges = generate_sample_ipv6_topology(num_stubs=400)

    print(f"[+] Rendering IPv6 AS Core visualization to {output_filename}...")
    render_as_core(
        nodes,
        edges,
        output_path=output_filename,
        dpi=300,
        title=plot_title,
        country=country,
        highlight_asns=highlight_asns,
    )
    print(f"[✓] IPv6 Visualization successfully saved to {output_filename}")


if __name__ == "__main__":
    main()
