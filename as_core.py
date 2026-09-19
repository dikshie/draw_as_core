"""
CAIDA-Style IPv4 AS Core Visualizer.

Implements the polar coordinate layout algorithm used by CAIDA to visualize
the macroscopic Internet topology and AS Core.
Supports loading and computing customer cones directly from CAIDA AS Relationships
datasets (e.g. *.as-rel2.txt or *.as-rel2.txt.bz2).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
import argparse
import bz2
import gzip
import math
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches


# Regional Internet Registry (RIR) color palette matching CAIDA theme
RIR_PALETTE = {
    "ARIN": "#3b82f6",     # Blue (North America)
    "RIPE": "#ef4444",     # Red (Europe / Middle East / Central Asia)
    "APNIC": "#10b981",    # Emerald Green (Asia Pacific)
    "LACNIC": "#f59e0b",   # Amber / Orange (Latin America & Caribbean)
    "AFRINIC": "#8b5cf6",  # Purple (Africa)
    "UNKNOWN": "#9ca3af"   # Muted Grey
}

# Well-known major AS names and specific longitudes
WELL_KNOWN_ASES = {
    3356:  ("Lumen / Level 3", "ARIN", -105.0),
    174:   ("Cogent", "ARIN", -77.0),
    1299:  ("Arelion (Telia)", "RIPE", 18.0),
    2914:  ("NTT Comms", "APNIC", 139.7),
    6939:  ("Hurricane Electric", "ARIN", -121.9),
    3257:  ("GTT Comms", "ARIN", -77.1),
    6453:  ("Tata Comms", "APNIC", 72.8),
    6762:  ("Telecom Italia Sparkle", "RIPE", 12.5),
    1273:  ("Vodafone / CW", "RIPE", -0.1),
    701:   ("Verizon", "ARIN", -77.0),
    5511:  ("Orange", "RIPE", 2.3),
    6461:  ("Zayo", "ARIN", -105.2),
    15169: ("Google", "ARIN", -122.0),
    13335: ("Cloudflare", "ARIN", -122.4),
    16509: ("Amazon AWS", "ARIN", -122.3),
    8075:  ("Microsoft", "ARIN", -122.1),
    20940: ("Akamai", "ARIN", -71.1),
    27699: ("Telecom Brasil", "LACNIC", -47.9),
    2609:  ("Antel Uruguay", "LACNIC", -56.2),
    37100: ("SEACOM Africa", "AFRINIC", 28.0),
    36903: ("Liquid Telecom", "AFRINIC", 31.0),
    2497:  ("IIJ", "APNIC", 139.7),
    4755:  ("TATA India", "APNIC", 77.2),
    4837:  ("China Unicom", "APNIC", 116.4),
    4134:  ("Chinanet", "APNIC", 116.4),
    7575:  ("AARNet", "APNIC", 149.1),
}


@dataclass
class ASNode:
    asn: int
    name: str
    cone_size: int
    longitude: float
    rir: str = "UNKNOWN"
    r: float = field(init=False, default=1.0)
    theta: float = field(init=False, default=0.0)
    x: float = field(init=False, default=0.0)
    y: float = field(init=False, default=0.0)


def infer_rir_and_longitude(asn: int) -> Tuple[str, str, float]:
    """
    Infers Name, RIR, and approximate Longitude for an ASN based on
    well-known assignments and IANA/RIR delegation blocks.
    """
    if asn in WELL_KNOWN_ASES:
        name, rir, lon = WELL_KNOWN_ASES[asn]
        return name, rir, lon

    # IANA / RIR 16-bit and 32-bit allocation range heuristics
    # AFRINIC
    if (36864 <= asn <= 37887) or (327680 <= asn <= 328703):
        rir = "AFRINIC"
        # Africa longitude centroid ~ 20.0
        lon = 20.0 + (hash(str(asn)) % 30) - 15.0
    # APNIC
    elif (4608 <= asn <= 4864) or (7467 <= asn <= 7722) or (9216 <= asn <= 10239) or \
         (17408 <= asn <= 18431) or (23552 <= asn <= 24575) or (37888 <= asn <= 38911) or \
         (45056 <= asn <= 46079) or (55296 <= asn <= 56319) or (58368 <= asn <= 59391) or \
         (131072 <= asn <= 141311):
        rir = "APNIC"
        # Asia-Pacific longitude centroid ~ 105.0
        lon = 105.0 + (hash(str(asn)) % 70) - 35.0
    # LACNIC
    elif (27648 <= asn <= 28671) or (52224 <= asn <= 53247) or (61440 <= asn <= 62463) or \
         (262144 <= asn <= 272383):
        rir = "LACNIC"
        # Latin America longitude centroid ~ -55.0
        lon = -55.0 + (hash(str(asn)) % 40) - 20.0
    # RIPE NCC
    elif (1257 <= asn <= 1300) or (31744 <= asn <= 32767) or (33792 <= asn <= 35839) or \
         (38912 <= asn <= 39935) or (40960 <= asn <= 45055) or (47104 <= asn <= 52223) or \
         (56320 <= asn <= 58367) or (59392 <= asn <= 61439) or (196608 <= asn <= 212991):
        rir = "RIPE"
        # Europe longitude centroid ~ 15.0
        lon = 15.0 + (hash(str(asn)) % 40) - 20.0
    # ARIN (Default for legacy early allocations and North America blocks)
    else:
        rir = "ARIN"
        # North America longitude centroid ~ -95.0
        lon = -95.0 + (hash(str(asn)) % 50) - 25.0

    return f"AS{asn}", rir, float(lon)


def calculate_radius(cone_size: int, max_cone: int) -> float:
    """
    Calculate polar radial coordinate (r) from customer cone size using CAIDA's logarithmic formula:
    r = 1 - (log(cone + 1) / log(max_cone + 1))
    """
    if max_cone <= 0 or cone_size < 0:
        return 1.0
    cone_size = min(cone_size, max_cone)
    r = 1.0 - (math.log(cone_size + 1) / math.log(max_cone + 1))
    return float(np.clip(r, 0.0, 1.0))


def calculate_angle(longitude: float, offset_deg: float = 0.0) -> float:
    """Calculate angular coordinate (theta in radians) from longitude in degrees [-180, 180]."""
    lon_norm = ((longitude + 180.0) % 360.0) - 180.0
    return math.radians(lon_norm + offset_deg)


def polar_to_cartesian(r: float, theta: float) -> Tuple[float, float]:
    """Convert polar coordinate (r, theta) to Cartesian (x, y)."""
    return (r * math.cos(theta), r * math.sin(theta))


def compute_bezier_curve(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    bend_factor: float = 0.35,
    num_points: int = 25
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute a quadratic Bézier curve between two points (p1, p2)
    with control point pulled towards the core origin (0, 0).
    """
    x1, y1 = p1
    x2, y2 = p2
    
    cx = bend_factor * (x1 + x2)
    cy = bend_factor * (y1 + y2)
    
    t = np.linspace(0, 1, num_points)
    bx = (1 - t)**2 * x1 + 2 * (1 - t) * t * cx + t**2 * x2
    by = (1 - t)**2 * y1 + 2 * (1 - t) * t * cy + t**2 * y2
    return bx, by


def compute_customer_cones(customer_graph: Dict[int, List[int]]) -> Dict[int, int]:
    """
    Computes transitive customer cone size for each provider AS in the customer DAG.
    Customer cone is the set of all ASes reachable following provider -> customer edges.
    """
    cone_sizes: Dict[int, int] = {}
    for provider in customer_graph:
        visited: Set[int] = set()
        stack = [provider]
        while stack:
            curr = stack.pop()
            for child in customer_graph.get(curr, []):
                if child not in visited:
                    visited.add(child)
                    stack.append(child)
        cone_sizes[provider] = len(visited)
    return cone_sizes


def load_caida_as_rel(file_path: str) -> Tuple[Dict[int, List[int]], List[Tuple[int, int]]]:
    """
    Parses a CAIDA AS Relationships dataset (*.as-rel2.txt or *.as-rel2.txt.bz2).
    Returns (customer_graph, all_edges).
    """
    customer_graph: Dict[int, List[int]] = {}
    all_edges: List[Tuple[int, int]] = []

    if file_path.endswith(".bz2"):
        open_fn = lambda p: bz2.open(p, "rt", encoding="utf-8", errors="ignore")
    elif file_path.endswith(".gz"):
        open_fn = lambda p: gzip.open(p, "rt", encoding="utf-8", errors="ignore")
    else:
        open_fn = lambda p: open(p, "rt", encoding="utf-8", errors="ignore")

    with open_fn(file_path) as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.strip().split("|")
            if len(parts) >= 3:
                try:
                    u, v, rel = int(parts[0]), int(parts[1]), int(parts[2])
                    all_edges.append((u, v))
                    if rel == -1:  # u is provider of v
                        if u not in customer_graph:
                            customer_graph[u] = []
                        customer_graph[u].append(v)
                except ValueError:
                    continue

    return customer_graph, all_edges


def prepare_graph_coordinates(
    nodes: Dict[int, ASNode],
    offset_deg: float = 0.0
) -> Dict[int, ASNode]:
    """Compute polar and Cartesian coordinates for all nodes."""
    if not nodes:
        return nodes
        
    max_cone = max(node.cone_size for node in nodes.values())
    
    for node in nodes.values():
        node.r = calculate_radius(node.cone_size, max_cone)
        node.theta = calculate_angle(node.longitude, offset_deg=offset_deg)
        node.x, node.y = polar_to_cartesian(node.r, node.theta)
        
    return nodes


def build_topology_from_caida(
    file_path: str,
    top_n: int = 700
) -> Tuple[Dict[int, ASNode], List[Tuple[int, int]]]:
    """
    Loads CAIDA dataset, computes customer cones, selects top_n ASes by rank,
    and returns nodes and induced edges for plotting.
    """
    print(f"[*] Reading CAIDA dataset from {file_path}...")
    customer_graph, all_edges = load_caida_as_rel(file_path)
    print(f"[*] Loaded {len(all_edges)} relationships. Calculating customer cones...")
    
    cone_sizes = compute_customer_cones(customer_graph)
    
    # Sort ASes by customer cone size
    sorted_ases = sorted(cone_sizes.items(), key=lambda x: x[1], reverse=True)
    selected_asns = {asn for asn, _ in sorted_ases[:top_n]}
    
    # Always include prominent well-known ASes if present in edges
    for asn in WELL_KNOWN_ASES:
        selected_asns.add(asn)

    nodes: Dict[int, ASNode] = {}
    for asn in selected_asns:
        cone = cone_sizes.get(asn, 0)
        name, rir, lon = infer_rir_and_longitude(asn)
        nodes[asn] = ASNode(
            asn=asn,
            name=name,
            cone_size=cone,
            longitude=lon,
            rir=rir
        )

    # Filter edges between selected nodes
    induced_edges = [
        (u, v) for u, v in all_edges if u in nodes and v in nodes
    ]
    print(f"[*] Selected {len(nodes)} ASes and {len(induced_edges)} interconnecting links.")
    return nodes, induced_edges


def generate_sample_2020_topology(num_stubs: int = 350) -> Tuple[Dict[int, ASNode], List[Tuple[int, int]]]:
    """
    Generates a realistic representative dataset for the 2020 IPv4 AS Core.
    """
    nodes: Dict[int, ASNode] = {}
    for asn, (name, rir, lon) in WELL_KNOWN_ASES.items():
        cone = 42000 - len(nodes) * 1500
        nodes[asn] = ASNode(asn, name, max(cone, 1000), lon, rir)

    edges: List[Tuple[int, int]] = [
        (3356, 174), (3356, 1299), (3356, 2914), (3356, 6939), (3356, 6453), (3356, 3257),
        (174, 1299), (174, 2914), (174, 6939), (174, 6453), (174, 3257),
        (1299, 2914), (1299, 6939), (1299, 6762), (1299, 1273),
        (2914, 6453), (2914, 6762), (6453, 3257), (6762, 1273),
        (15169, 3356), (15169, 1299), (15169, 2914), (15169, 174), (15169, 6939),
        (13335, 174), (13335, 3356), (13335, 1299), (13335, 6939),
        (16509, 3356), (16509, 1299), (16509, 2914),
        (8075, 3356), (8075, 1299), (8075, 174),
        (20940, 3356), (20940, 174), (20940, 6939),
        (27699, 3356), (27699, 174), (27699, 1299),
        (2609, 3356), (2609, 27699),
        (37100, 1299), (37100, 6453), (37100, 3356),
        (36903, 1299), (36903, 37100),
    ]

    np.random.seed(42)
    tier1_keys = [3356, 174, 1299, 2914, 6939, 6453, 3257]
    for i in range(1000, 1000 + num_stubs):
        name, rir, lon = infer_rir_and_longitude(i)
        cone = int(np.random.exponential(scale=35))
        nodes[i] = ASNode(i, name, cone, lon, rir)
        num_upstreams = np.random.choice([1, 2, 3], p=[0.7, 0.22, 0.08])
        upstreams = np.random.choice(tier1_keys, size=num_upstreams, replace=False)
        for up in upstreams:
            edges.append((i, int(up)))

    return nodes, edges


def render_as_core(
    nodes: Dict[int, ASNode],
    edges: List[Tuple[int, int]],
    output_path: str = "as_core_2020.png",
    dpi: int = 300,
    title: str = "CAIDA IPv4 AS Core Visualization"
) -> plt.Figure:
    """
    Renders the polar AS Core map replicating CAIDA's aesthetic and coordinate system.
    """
    prepare_graph_coordinates(nodes)

    fig, ax = plt.subplots(figsize=(13, 13), facecolor="#090d16")
    ax.set_facecolor("#090d16")

    # 1. Concentric circles (Hierarchy guide)
    for radius in [0.2, 0.4, 0.6, 0.8, 1.0]:
        circle = patches.Circle(
            (0, 0), radius,
            fill=False,
            color="#1e293b",
            linestyle="--",
            linewidth=0.8,
            alpha=0.7
        )
        ax.add_patch(circle)

    # 2. Geographic longitude axes
    for angle_deg in range(0, 360, 45):
        rad = math.radians(angle_deg)
        ax.plot([0, 1.05 * math.cos(rad)], [0, 1.05 * math.sin(rad)],
                color="#1e293b", linestyle=":", linewidth=0.6, alpha=0.5)

    # Sector labels on perimeter
    region_positions = [
        ("NORTH AMERICA\n(ARIN)", math.radians(-95)),
        ("EUROPE\n(RIPE)", math.radians(15)),
        ("AFRICA\n(AFRINIC)", math.radians(25)),
        ("ASIA PACIFIC\n(APNIC)", math.radians(110)),
        ("LATIN AMERICA\n(LACNIC)", math.radians(-55)),
    ]
    for label, theta in region_positions:
        lx, ly = 1.12 * math.cos(theta), 1.12 * math.sin(theta)
        ax.text(lx, ly, label, color="#64748b", fontsize=8, ha="center", va="center", weight="bold")

    # 3. Curved Bézier links
    for u, v in edges:
        if u in nodes and v in nodes:
            n1, n2 = nodes[u], nodes[v]
            bx, by = compute_bezier_curve((n1.x, n1.y), (n2.x, n2.y), bend_factor=0.32, num_points=20)
            coreness = 1.0 - min(n1.r, n2.r)
            link_alpha = 0.05 + 0.35 * (coreness ** 2)
            ax.plot(bx, by, color="#38bdf8", alpha=link_alpha, linewidth=0.5)

    # 4. Draw Nodes
    for node in nodes.values():
        color = RIR_PALETTE.get(node.rir, RIR_PALETTE["UNKNOWN"])
        node_size = 12.0 + 130.0 * ((1.0 - node.r) ** 2.2)
        node_alpha = 0.45 + 0.55 * (1.0 - node.r)
        ax.scatter(
            node.x, node.y,
            color=color,
            s=node_size,
            alpha=node_alpha,
            edgecolors="#ffffff" if node.r < 0.25 else "none",
            linewidths=0.5,
            zorder=3
        )

    # 5. Core Labels
    prominent = [3356, 174, 1299, 2914, 6939, 3257, 6453, 15169, 13335, 27699, 37100]
    for asn in prominent:
        if asn in nodes:
            n = nodes[asn]
            ax.text(
                n.x, n.y + 0.025,
                f"{n.name}\n(AS{n.asn})",
                color="#ffffff",
                fontsize=7,
                ha="center",
                va="bottom",
                weight="bold",
                bbox=dict(boxstyle="round,pad=0.15", fc="#090d16", ec="#334155", lw=0.5, alpha=0.85),
                zorder=4
            )

    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.axis("off")

    legend_handles = [
        patches.Patch(facecolor=color, edgecolor="#334155", label=rir)
        for rir, color in RIR_PALETTE.items() if rir != "UNKNOWN"
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        facecolor="#0f172a",
        edgecolor="#334155",
        labelcolor="#e2e8f0",
        title="Regional Registries",
        title_fontsize=9,
        fontsize=8,
        framealpha=0.9
    )

    ax.text(0, 1.20, title, color="#f8fafc", fontsize=14, ha="center", weight="bold")
    ax.text(
        0, -1.22,
        r"$\mathrm{Radial\ position:}\ r = 1 - \frac{\log(\mathrm{CustomerCone} + 1)}{\log(\mathrm{MaxCone} + 1)} \quad\vert\quad \mathrm{Angular\ position:}\ \theta = \mathrm{Longitude}$",
        color="#94a3b8", fontsize=9, ha="center"
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor(), edgecolor="none")
    return fig


def main():
    parser = argparse.ArgumentParser(description="CAIDA IPv4 AS Core Visualizer")
    parser.add_argument("-i", "--input", help="Path to CAIDA *.as-rel2.txt or *.as-rel2.txt.bz2 file", default=None)
    parser.add_argument("-n", "--top", help="Top N ASes to visualize by customer cone", type=int, default=700)
    parser.add_argument("-o", "--output", help="Output PNG path", default="as_core_caida.png")
    parser.add_argument("-t", "--title", help="Plot title", default="CAIDA IPv4 AS Core Topology")
    args = parser.parse_args()

    # Automatically check for local CAIDA dataset if no argument passed
    caida_default = "20260901.as-rel2.txt"
    if args.input is None and os.path.exists(caida_default):
        args.input = caida_default

    if args.input and os.path.exists(args.input):
        nodes, edges = build_topology_from_caida(args.input, top_n=args.top)
        title = f"{args.title} ({os.path.basename(args.input)})"
    else:
        print("[!] No CAIDA dataset specified or found. Using realistic simulation...")
        nodes, edges = generate_sample_2020_topology(num_stubs=400)
        title = args.title

    print(f"[+] Rendering AS Core visualization to {args.output}...")
    render_as_core(nodes, edges, output_path=args.output, dpi=300, title=title)
    print(f"[✓] Visualization successfully saved to {args.output}")


if __name__ == "__main__":
    main()
