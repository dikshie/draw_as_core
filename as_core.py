"""
CAIDA-Style IPv4 AS Core Visualizer.

Implements the polar coordinate layout algorithm used by CAIDA to visualize
the macroscopic Internet topology and AS Core.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import math
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


def calculate_radius(cone_size: int, max_cone: int) -> float:
    """
    Calculate polar radial coordinate (r) from customer cone size using CAIDA's logarithmic formula:
    r = 1 - (log(cone + 1) / log(max_cone + 1))
    
    Center (r=0) is the core Tier-1 providers with largest customer cone.
    Perimeter (r=1) is the edge/stub ASes with zero customer cone.
    """
    if max_cone <= 0 or cone_size < 0:
        return 1.0
    cone_size = min(cone_size, max_cone)
    r = 1.0 - (math.log(cone_size + 1) / math.log(max_cone + 1))
    return float(np.clip(r, 0.0, 1.0))


def calculate_angle(longitude: float, offset_deg: float = 0.0) -> float:
    """
    Calculate angular coordinate (theta in radians) from longitude in degrees [-180, 180].
    """
    # Normalize longitude to [-180, 180]
    lon_norm = ((longitude + 180.0) % 360.0) - 180.0
    return math.radians(lon_norm + offset_deg)


def polar_to_cartesian(r: float, theta: float) -> Tuple[float, float]:
    """Convert polar coordinate (r, theta) to Cartesian (x, y)."""
    return (r * math.cos(theta), r * math.sin(theta))


def compute_bezier_curve(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    bend_factor: float = 0.35,
    num_points: int = 30
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute a quadratic Bézier curve between two points (p1, p2)
    with control point pulled towards the core origin (0, 0).
    """
    x1, y1 = p1
    x2, y2 = p2
    
    # Control point biased toward center (0, 0)
    cx = bend_factor * (x1 + x2)
    cy = bend_factor * (y1 + y2)
    
    t = np.linspace(0, 1, num_points)
    bx = (1 - t)**2 * x1 + 2 * (1 - t) * t * cx + t**2 * x2
    by = (1 - t)**2 * y1 + 2 * (1 - t) * t * cy + t**2 * y2
    return bx, by


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


def generate_sample_2020_topology(num_stubs: int = 350) -> Tuple[Dict[int, ASNode], List[Tuple[int, int]]]:
    """
    Generates a realistic representative dataset for the 2020 IPv4 AS Core.
    Includes major Tier-1/Tier-2 backbones, hyperscalers, regional backbones, and stubs.
    """
    nodes: Dict[int, ASNode] = {
        # Tier-1 and Major Global Backbones (ARIN, RIPE, APNIC)
        3356:  ASNode(3356, "Lumen / Level 3", 42000, -105.0, "ARIN"),
        174:   ASNode(174, "Cogent", 38000, -77.0, "ARIN"),
        1299:  ASNode(1299, "Arelion (Telia)", 35000, 18.0, "RIPE"),
        2914:  ASNode(2914, "NTT Communications", 29000, 139.7, "APNIC"),
        6939:  ASNode(6939, "Hurricane Electric", 31000, -121.9, "ARIN"),
        6453:  ASNode(6453, "Tata Communications", 24000, 72.8, "APNIC"),
        3257:  ASNode(3257, "GTT Communications", 22000, -77.1, "ARIN"),
        6762:  ASNode(6762, "Telecom Italia Sparkle", 18000, 12.5, "RIPE"),
        1273:  ASNode(1273, "Vodafone / CW", 16000, -0.1, "RIPE"),
        
        # Hyperscalers & CDNs
        15169: ASNode(15169, "Google", 16500, -122.0, "ARIN"),
        13335: ASNode(13335, "Cloudflare", 12000, -122.4, "ARIN"),
        16509: ASNode(16509, "Amazon AWS", 14000, -122.3, "ARIN"),
        8075:  ASNode(8075, "Microsoft", 13000, -122.1, "ARIN"),
        20940: ASNode(20940, "Akamai", 7500, -71.1, "ARIN"),
        
        # Regional Backbones (LACNIC & AFRINIC)
        27699: ASNode(27699, "Telecom Brasil", 4500, -47.9, "LACNIC"),
        2609:  ASNode(2609, "Antel Uruguay", 2100, -56.2, "LACNIC"),
        37100: ASNode(37100, "SEACOM Africa", 2800, 28.0, "AFRINIC"),
        36903: ASNode(36903, "Liquid Telecom", 3400, 31.0, "AFRINIC"),
    }

    edges: List[Tuple[int, int]] = [
        # Full mesh core interconnects
        (3356, 174), (3356, 1299), (3356, 2914), (3356, 6939), (3356, 6453), (3356, 3257),
        (174, 1299), (174, 2914), (174, 6939), (174, 6453), (174, 3257),
        (1299, 2914), (1299, 6939), (1299, 6762), (1299, 1273),
        (2914, 6453), (2914, 6762), (6453, 3257), (6762, 1273),
        
        # Hyperscalers connected to Tier-1s
        (15169, 3356), (15169, 1299), (15169, 2914), (15169, 174), (15169, 6939),
        (13335, 174), (13335, 3356), (13335, 1299), (13335, 6939),
        (16509, 3356), (16509, 1299), (16509, 2914),
        (8075, 3356), (8075, 1299), (8075, 174),
        (20940, 3356), (20940, 174), (20940, 6939),
        
        # Regional Backbones
        (27699, 3356), (27699, 174), (27699, 1299),
        (2609, 3356), (2609, 27699),
        (37100, 1299), (37100, 6453), (37100, 3356),
        (36903, 1299), (36903, 37100),
    ]

    # Stubs & edge ASes distribution
    np.random.seed(42)
    rir_probs = [0.34, 0.32, 0.20, 0.09, 0.05]
    rirs = ["ARIN", "RIPE", "APNIC", "LACNIC", "AFRINIC"]
    lon_ranges = {
        "ARIN": (-125, -65),
        "RIPE": (-10, 45),
        "APNIC": (60, 150),
        "LACNIC": (-80, -35),
        "AFRINIC": (10, 40)
    }

    tier1_keys = [3356, 174, 1299, 2914, 6939, 6453, 3257]
    
    for i in range(1000, 1000 + num_stubs):
        selected_rir = np.random.choice(rirs, p=rir_probs)
        lon = float(np.random.uniform(*lon_ranges[selected_rir]))
        # Exponential distribution for customer cone (most have small or 0 cone)
        cone = int(np.random.exponential(scale=35))
        nodes[i] = ASNode(
            asn=i,
            name=f"AS{i}",
            cone_size=cone,
            longitude=lon,
            rir=selected_rir
        )
        # Connect to 1-3 upstream transit providers
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
    title: str = "CAIDA IPv4 AS Core (2020 Snapshot Simulation)"
) -> plt.Figure:
    """
    Renders the polar AS Core map replicating CAIDA's aesthetic and coordinate system.
    """
    # Ensure coordinates are populated
    prepare_graph_coordinates(nodes)

    fig, ax = plt.subplots(figsize=(13, 13), facecolor="#090d16")
    ax.set_facecolor("#090d16")

    # 1. Draw polar concentric circles (Hierarchy: Core -> Periphery)
    radii = [0.2, 0.4, 0.6, 0.8, 1.0]
    for radius in radii:
        circle = patches.Circle(
            (0, 0), radius,
            fill=False,
            color="#1e293b",
            linestyle="--",
            linewidth=0.8,
            alpha=0.7
        )
        ax.add_patch(circle)

    # 2. Draw geographic longitude axes guides
    for angle_deg in range(0, 360, 45):
        rad = math.radians(angle_deg)
        x_end = 1.05 * math.cos(rad)
        y_end = 1.05 * math.sin(rad)
        ax.plot([0, x_end], [0, y_end], color="#1e293b", linestyle=":", linewidth=0.6, alpha=0.5)

    # Add Region Sector Labels on the perimeter
    region_positions = [
        ("NORTH AMERICA\n(ARIN)", math.radians(-95)),
        ("EUROPE\n(RIPE)", math.radians(15)),
        ("AFRICA\n(AFRINIC)", math.radians(25)),
        ("ASIA PACIFIC\n(APNIC)", math.radians(110)),
        ("LATIN AMERICA\n(LACNIC)", math.radians(-55)),
    ]
    for label, theta in region_positions:
        lx, ly = 1.12 * math.cos(theta), 1.12 * math.sin(theta)
        ax.text(lx, ly, label, color="#64748b", fontsize=8, ha="center", va="center", weight="semibold")

    # 3. Draw curved links (Bézier curves)
    for u, v in edges:
        if u in nodes and v in nodes:
            n1, n2 = nodes[u], nodes[v]
            bx, by = compute_bezier_curve((n1.x, n1.y), (n2.x, n2.y), bend_factor=0.32, num_points=25)
            
            # Shading by hierarchy (links to deep core are brighter)
            coreness = 1.0 - min(n1.r, n2.r)
            link_alpha = 0.08 + 0.30 * (coreness ** 2)
            ax.plot(bx, by, color="#38bdf8", alpha=link_alpha, linewidth=0.6)

    # 4. Draw AS Nodes
    for node in nodes.values():
        color = RIR_PALETTE.get(node.rir, RIR_PALETTE["UNKNOWN"])
        # Size nodes proportionally to core centrality
        node_size = 14.0 + 130.0 * ((1.0 - node.r) ** 2.2)
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

    # 5. Add Labels for prominent Core ASes
    prominent_asns = [3356, 174, 1299, 2914, 6939, 15169, 13335, 6453, 37100, 27699]
    for asn in prominent_asns:
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

    # Set viewport limits and styling
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.axis("off")

    # Legend for RIRs
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

    # Titles and Annotations
    ax.text(
        0, 1.20, title,
        color="#f8fafc", fontsize=14, ha="center", weight="bold"
    )
    ax.text(
        0, -1.22,
        r"$\mathrm{Radial\ position:}\ r = 1 - \frac{\log(\mathrm{CustomerCone} + 1)}{\log(\mathrm{MaxCone} + 1)} \quad\vert\quad \mathrm{Angular\ position:}\ \theta = \mathrm{Longitude}$",
        color="#94a3b8", fontsize=9, ha="center"
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, facecolor=fig.get_facecolor(), edgecolor="none")
    return fig


def main():
    print("[+] Generating sample 2020 IPv4 AS Core topology...")
    nodes, edges = generate_sample_2020_topology(num_stubs=400)
    output_filename = "as_core_2020.png"
    print(f"[+] Rendering AS Core map with {len(nodes)} ASes and {len(edges)} links...")
    render_as_core(nodes, edges, output_path=output_filename, dpi=300)
    print(f"[✓] Visualization successfully saved to {output_filename}")


if __name__ == "__main__":
    main()
