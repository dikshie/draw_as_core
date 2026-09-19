"""
CAIDA-Style IPv4 AS Core Visualizer.

Implements the polar coordinate layout algorithm used by CAIDA to visualize
the macroscopic Internet topology and AS Core.
Supports:
1. Global AS Core topology visualization.
2. Country-specific AS Core filtering and rendering (e.g. Indonesia - ID, US, JP, DE, SG).
3. Automatic RIR delegation fetching and offline fallback databases.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
import argparse
import bz2
import gzip
import math
import os
import urllib.request
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

# Regional color palette for Indonesian sectors
ID_SECTOR_PALETTE = {
    "Sumatra": "#3b82f6",          # Blue
    "Java": "#ef4444",             # Red
    "Kalimantan": "#10b981",       # Emerald Green
    "Bali & Nusa Tenggara": "#f59e0b", # Amber
    "Sulawesi": "#8b5cf6",         # Purple
    "Maluku & Papua": "#ec4899",   # Pink
    "Core / National": "#38bdf8"   # Sky Blue
}

# Well-known global major AS names
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

# Well-known Indonesian ASes with names and island regions
INDONESIA_WELL_KNOWN = {
    7713:   ("Telkom Indonesia", "Java", 106.8),
    4761:   ("Indosat Ooredoo Hutchison", "Java", 106.8),
    17451:  ("Biznet Networks", "Java", 106.8),
    24203:  ("XL Axiata", "Java", 106.8),
    23947:  ("Moratelindo", "Java", 106.8),
    7597:   ("APJII / IIX", "Java", 106.8),
    4795:   ("CBN", "Java", 106.8),
    55688:  ("MyRepublic ID", "Java", 106.8),
    23693:  ("Telkomsel", "Java", 106.8),
    9341:   ("Cyberindo Aditama (CBN)", "Java", 106.8),
    56023:  ("Link Net / FirstMedia", "Java", 106.8),
    45833:  ("Universitas Indonesia", "Java", 106.8),
    45842:  ("Institut Teknologi Bandung", "Java", 107.6),
    45839:  ("Universitas Gadjah Mada", "Java", 110.4),
    131759: ("Batam Bintan Telko", "Sumatra", 104.0),
    133481: ("Bali Fiber Optik", "Bali & Nusa Tenggara", 115.2),
    136052: ("Makassar Cyber Media", "Sulawesi", 119.4),
    138382: ("Papua Digital Net", "Maluku & Papua", 140.7),
    136050: ("Kalimantan Network", "Kalimantan", 114.6),
}


@dataclass
class ASNode:
    asn: int
    name: str
    cone_size: int
    longitude: float
    rir: str = "UNKNOWN"
    country: str = "GLOBAL"
    region: str = ""
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

    # IANA / RIR allocation range heuristics
    if (36864 <= asn <= 37887) or (327680 <= asn <= 328703):
        rir, lon = "AFRINIC", 20.0 + (hash(str(asn)) % 30) - 15.0
    elif (4608 <= asn <= 4864) or (7467 <= asn <= 7722) or (9216 <= asn <= 10239) or \
         (17408 <= asn <= 18431) or (23552 <= asn <= 24575) or (37888 <= asn <= 38911) or \
         (45056 <= asn <= 46079) or (55296 <= asn <= 56319) or (58368 <= asn <= 59391) or \
         (131072 <= asn <= 141311):
        rir, lon = "APNIC", 105.0 + (hash(str(asn)) % 70) - 35.0
    elif (27648 <= asn <= 28671) or (52224 <= asn <= 53247) or (61440 <= asn <= 62463) or \
         (262144 <= asn <= 272383):
        rir, lon = "LACNIC", -55.0 + (hash(str(asn)) % 40) - 20.0
    elif (1257 <= asn <= 1300) or (31744 <= asn <= 32767) or (33792 <= asn <= 35839) or \
         (38912 <= asn <= 39935) or (40960 <= asn <= 45055) or (47104 <= asn <= 52223) or \
         (56320 <= asn <= 58367) or (59392 <= asn <= 61439) or (196608 <= asn <= 212991):
        rir, lon = "RIPE", 15.0 + (hash(str(asn)) % 40) - 20.0
    else:
        rir, lon = "ARIN", -95.0 + (hash(str(asn)) % 50) - 25.0

    return f"AS{asn}", rir, float(lon)


def infer_indonesia_region(asn: int) -> Tuple[str, str, float]:
    """Infers Name, Island Region, and Longitude for Indonesian ASes."""
    if asn in INDONESIA_WELL_KNOWN:
        name, region, lon = INDONESIA_WELL_KNOWN[asn]
        return name, region, lon

    # Derive realistic island distribution for Indonesian ASNs
    seed = hash(str(asn))
    region_choice = seed % 100
    if region_choice < 55:
        region = "Java"
        lon = 106.0 + (seed % 80) / 10.0  # 106 to 114
    elif region_choice < 72:
        region = "Sumatra"
        lon = 95.5 + (seed % 90) / 10.0   # 95.5 to 104.5
    elif region_choice < 82:
        region = "Kalimantan"
        lon = 109.0 + (seed % 75) / 10.0  # 109 to 116.5
    elif region_choice < 90:
        region = "Sulawesi"
        lon = 119.5 + (seed % 50) / 10.0  # 119.5 to 124.5
    elif region_choice < 96:
        region = "Bali & Nusa Tenggara"
        lon = 115.0 + (seed % 90) / 10.0  # 115 to 124
    else:
        region = "Maluku & Papua"
        lon = 126.0 + (seed % 140) / 10.0 # 126 to 140

    return f"AS{asn}", region, float(lon)


def fetch_country_asns(country_code: str, cache_dir: str = "data") -> Set[int]:
    """
    Retrieves the set of ASNs registered in a specific country (e.g. ID, US, JP, DE).
    Uses RIR delegated statistics with local disk caching and offline fallbacks.
    """
    country_code = country_code.upper()
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"delegated_{country_code}.txt")

    # If cached, load from disk
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return {int(line.strip()) for line in f if line.strip().isdigit()}

    # Select RIR delegation source based on country
    rir_urls = {
        "APNIC": "https://ftp.apnic.net/stats/apnic/delegated-apnic-latest",
        "RIPE": "https://ftp.ripe.net/ripe/stats/delegated-ripencc-latest",
        "ARIN": "https://ftp.arin.net/pub/stats/arin/delegated-arin-extended-latest",
        "LACNIC": "https://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest",
        "AFRINIC": "https://ftp.afrinic.net/pub/stats/afrinic/delegated-afrinic-latest",
    }

    country_to_rir = {
        "ID": "APNIC", "JP": "APNIC", "SG": "APNIC", "AU": "APNIC", "IN": "APNIC", "CN": "APNIC",
        "DE": "RIPE", "GB": "RIPE", "FR": "RIPE", "NL": "RIPE", "IT": "RIPE", "RU": "RIPE",
        "US": "ARIN", "CA": "ARIN",
        "BR": "LACNIC", "AR": "LACNIC", "CL": "LACNIC", "MX": "LACNIC",
        "ZA": "AFRINIC", "NG": "AFRINIC", "KE": "AFRINIC", "EG": "AFRINIC"
    }

    selected_rir = country_to_rir.get(country_code, "APNIC")
    url = rir_urls.get(selected_rir, rir_urls["APNIC"])

    asns: Set[int] = set()
    try:
        print(f"[*] Querying {selected_rir} delegation statistics for country '{country_code}'...")
        req = urllib.request.Request(url, headers={"User-Agent": "CAIDA-AS-Core-Visualizer/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", errors="ignore")
                if f"|{country_code}|asn|" in line:
                    parts = line.strip().split("|")
                    if len(parts) >= 5:
                        start_asn, count = int(parts[3]), int(parts[4])
                        for a in range(start_asn, start_asn + count):
                            asns.add(a)
        
        # Cache to disk
        with open(cache_file, "w", encoding="utf-8") as f:
            for a in sorted(asns):
                f.write(f"{a}\n")
        print(f"[+] Loaded {len(asns)} ASNs for country '{country_code}'.")
    except Exception as e:
        print(f"[!] Warning: Remote delegation fetch skipped ({e}). Using offline database.")
        if country_code == "ID":
            asns = set(INDONESIA_WELL_KNOWN.keys())

    return asns


def calculate_radius(cone_size: int, max_cone: int) -> float:
    """Calculate polar radial coordinate (r) from customer cone size."""
    if max_cone <= 0 or cone_size < 0:
        return 1.0
    cone_size = min(cone_size, max_cone)
    r = 1.0 - (math.log(cone_size + 1) / math.log(max_cone + 1))
    return float(np.clip(r, 0.0, 1.0))


def calculate_angle(longitude: float, offset_deg: float = 0.0, country: str = "GLOBAL") -> float:
    """Calculate angular coordinate (theta in radians)."""
    if country == "ID":
        # Linearly project Indonesia's longitude (95°E - 141°E) across the full 360° circle
        lon_clamped = max(95.0, min(141.0, longitude))
        ratio = (lon_clamped - 95.0) / (141.0 - 95.0)
        theta = ratio * 2 * math.pi - math.pi / 2
        return theta

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
    """Compute a quadratic Bézier curve pulling inward toward the origin (0, 0)."""
    x1, y1 = p1
    x2, y2 = p2
    cx = bend_factor * (x1 + x2)
    cy = bend_factor * (y1 + y2)
    t = np.linspace(0, 1, num_points)
    bx = (1 - t)**2 * x1 + 2 * (1 - t) * t * cx + t**2 * x2
    by = (1 - t)**2 * y1 + 2 * (1 - t) * t * cy + t**2 * y2
    return bx, by


def compute_customer_cones(customer_graph: Dict[int, List[int]]) -> Dict[int, int]:
    """Computes transitive customer cone size for each provider AS in the customer DAG."""
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
    """Parses a CAIDA AS Relationships dataset (*.as-rel2.txt or *.as-rel2.txt.bz2)."""
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
                    if rel == -1:
                        if u not in customer_graph:
                            customer_graph[u] = []
                        customer_graph[u].append(v)
                except ValueError:
                    continue

    return customer_graph, all_edges


def prepare_graph_coordinates(
    nodes: Dict[int, ASNode],
    country: str = "GLOBAL",
    offset_deg: float = 0.0
) -> Dict[int, ASNode]:
    """Compute polar and Cartesian coordinates for all nodes."""
    if not nodes:
        return nodes
        
    max_cone = max((node.cone_size for node in nodes.values()), default=1)
    
    for node in nodes.values():
        node.r = calculate_radius(node.cone_size, max_cone)
        node.theta = calculate_angle(node.longitude, offset_deg=offset_deg, country=country)
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
    
    sorted_ases = sorted(cone_sizes.items(), key=lambda x: x[1], reverse=True)
    selected_asns = {asn for asn, _ in sorted_ases[:top_n]}
    
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

    induced_edges = [
        (u, v) for u, v in all_edges if u in nodes and v in nodes
    ]
    print(f"[*] Selected {len(nodes)} ASes and {len(induced_edges)} interconnecting links.")
    return nodes, induced_edges


def generate_sample_2020_topology(num_stubs: int = 350) -> Tuple[Dict[int, ASNode], List[Tuple[int, int]]]:
    """Generates a realistic representative global topology."""
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


def build_country_topology(
    file_path: Optional[str],
    country_code: str = "ID",
    top_n: int = 600
) -> Tuple[Dict[int, ASNode], List[Tuple[int, int]]]:
    """
    Builds a country-specific AS Core topology from CAIDA dataset or local simulation.
    """
    country_code = country_code.upper()
    country_asns = fetch_country_asns(country_code)

    if file_path and os.path.exists(file_path):
        print(f"[*] Loading CAIDA dataset from {file_path} for country '{country_code}'...")
        customer_graph, all_edges = load_caida_as_rel(file_path)
        cone_sizes = compute_customer_cones(customer_graph)
    else:
        print(f"[*] Generating simulated topology for country '{country_code}'...")
        customer_graph = {}
        all_edges = []
        cone_sizes = {}
        if country_code == "ID":
            country_asns = set(INDONESIA_WELL_KNOWN.keys()) | set(range(131000, 131300))
            for asn in country_asns:
                cone_sizes[asn] = 450 if asn == 7713 else (350 if asn == 4761 else (250 if asn == 17451 else int(np.random.exponential(15))))
                all_edges.append((asn, 7713))
                if np.random.rand() > 0.5:
                    all_edges.append((asn, 4761))

    # Filter for country ASNs
    valid_country_asns = {
        asn for asn in country_asns
        if asn in cone_sizes or any(u == asn or v == asn for u, v in all_edges)
    }

    # Sort by customer cone size
    sorted_country_ases = sorted(
        [(asn, cone_sizes.get(asn, 0)) for asn in valid_country_asns],
        key=lambda x: x[1], reverse=True
    )
    selected_asns = {asn for asn, _ in sorted_country_ases[:top_n]}

    if country_code == "ID":
        for asn in INDONESIA_WELL_KNOWN:
            selected_asns.add(asn)

    nodes: Dict[int, ASNode] = {}
    for asn in selected_asns:
        cone = cone_sizes.get(asn, 0)
        if country_code == "ID":
            name, region, lon = infer_indonesia_region(asn)
            rir = "APNIC"
        else:
            name, rir, lon = infer_rir_and_longitude(asn)
            region = country_code

        nodes[asn] = ASNode(
            asn=asn,
            name=name,
            cone_size=cone,
            longitude=lon,
            rir=rir,
            country=country_code,
            region=region
        )

    # Filter internal country interconnects
    induced_edges = [
        (u, v) for u, v in all_edges if u in nodes and v in nodes
    ]
    print(f"[+] Selected {len(nodes)} {country_code} ASes and {len(induced_edges)} domestic links.")
    return nodes, induced_edges


def render_as_core(
    nodes: Dict[int, ASNode],
    edges: List[Tuple[int, int]],
    output_path: str = "as_core.png",
    dpi: int = 300,
    title: str = "IPv4 AS Core Visualization",
    country: str = "GLOBAL"
) -> plt.Figure:
    """Renders the polar AS Core map replicating CAIDA's aesthetic."""
    prepare_graph_coordinates(nodes, country=country)

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

    # 2. Draw sector axes & labels
    if country == "ID":
        # Indonesia Island Sectors
        id_sectors = [
            ("SUMATRA", math.radians(-60)),
            ("JAVA", math.radians(0)),
            ("KALIMANTAN", math.radians(60)),
            ("BALI & NUSA TENGGARA", math.radians(120)),
            ("SULAWESI", math.radians(180)),
            ("MALUKU & PAPUA", math.radians(240)),
        ]
        for label, theta in id_sectors:
            lx, ly = 1.12 * math.cos(theta), 1.12 * math.sin(theta)
            ax.plot([0, 1.05 * math.cos(theta)], [0, 1.05 * math.sin(theta)],
                    color="#1e293b", linestyle=":", linewidth=0.6, alpha=0.5)
            ax.text(lx, ly, label, color="#64748b", fontsize=8, ha="center", va="center", weight="bold")
    else:
        # Global Sectors
        global_sectors = [
            ("NORTH AMERICA\n(ARIN)", math.radians(-95)),
            ("EUROPE\n(RIPE)", math.radians(15)),
            ("AFRICA\n(AFRINIC)", math.radians(25)),
            ("ASIA PACIFIC\n(APNIC)", math.radians(110)),
            ("LATIN AMERICA\n(LACNIC)", math.radians(-55)),
        ]
        for label, theta in global_sectors:
            lx, ly = 1.12 * math.cos(theta), 1.12 * math.sin(theta)
            ax.plot([0, 1.05 * math.cos(theta)], [0, 1.05 * math.sin(theta)],
                    color="#1e293b", linestyle=":", linewidth=0.6, alpha=0.5)
            ax.text(lx, ly, label, color="#64748b", fontsize=8, ha="center", va="center", weight="bold")

    # 3. Curved Bézier links
    for u, v in edges:
        if u in nodes and v in nodes:
            n1, n2 = nodes[u], nodes[v]
            bx, by = compute_bezier_curve((n1.x, n1.y), (n2.x, n2.y), bend_factor=0.32, num_points=20)
            coreness = 1.0 - min(n1.r, n2.r)
            link_alpha = 0.06 + 0.38 * (coreness ** 2)
            ax.plot(bx, by, color="#38bdf8", alpha=link_alpha, linewidth=0.5)

    # 4. Draw Nodes
    for node in nodes.values():
        if country == "ID":
            color = ID_SECTOR_PALETTE.get(node.region, ID_SECTOR_PALETTE["Core / National"])
        else:
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

    # 5. Add Radial Callout Annotations for Top Core ASes (prevents text collision at center)
    top_labeled = sorted(nodes.values(), key=lambda n: n.cone_size, reverse=True)[:6]
    num_labels = len(top_labeled)
    for idx, n in enumerate(top_labeled):
        # Distribute callout boxes evenly around an orbit ring at r=0.28
        callout_angle = (2.0 * math.pi * idx / max(num_labels, 1)) - (math.pi / 2.0)
        callout_r = 0.28
        cx = callout_r * math.cos(callout_angle)
        cy = callout_r * math.sin(callout_angle)
        
        # Display clean short name
        display_name = n.name
        if len(display_name) > 20:
            display_name = display_name[:18] + ".."

        if n.name == f"AS{n.asn}" or n.name.startswith(f"AS{n.asn}"):
            label_text = f"AS{n.asn}"
        else:
            label_text = f"{display_name}\n(AS{n.asn})"

        ax.annotate(
            label_text,
            xy=(n.x, n.y),
            xytext=(cx, cy),
            textcoords="data",
            ha="center",
            va="center",
            fontsize=5.5,
            color="#ffffff",
            weight="semibold",
            bbox=dict(boxstyle="round,pad=0.2", fc="#090d16", ec="#38bdf8", lw=0.6, alpha=0.92),
            arrowprops=dict(
                arrowstyle="-|>",
                color="#38bdf8",
                lw=0.6,
                alpha=0.65,
                mutation_scale=6,
                connectionstyle="arc3,rad=0.08"
            ),
            zorder=5
        )

    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.axis("off")

    # Legend
    if country == "ID":
        legend_handles = [
            patches.Patch(facecolor=col, edgecolor="#334155", label=reg)
            for reg, col in ID_SECTOR_PALETTE.items()
        ]
        legend_title = "Island Regions"
    else:
        legend_handles = [
            patches.Patch(facecolor=col, edgecolor="#334155", label=rir)
            for rir, col in RIR_PALETTE.items() if rir != "UNKNOWN"
        ]
        legend_title = "Regional Registries"

    ax.legend(
        handles=legend_handles,
        loc="lower right",
        facecolor="#0f172a",
        edgecolor="#334155",
        labelcolor="#e2e8f0",
        title=legend_title,
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
    parser = argparse.ArgumentParser(description="CAIDA IPv4 AS Core Visualizer (Global & Country-Level)")
    parser.add_argument("-i", "--input", help="Path to CAIDA *.as-rel2.txt or *.as-rel2.txt.bz2 file", default=None)
    parser.add_argument("-c", "--country", help="2-letter ISO Country Code (e.g. ID, US, JP, DE, SG) or 'GLOBAL'", default=None)
    parser.add_argument("-n", "--top", help="Top N ASes to visualize by customer cone", type=int, default=700)
    parser.add_argument("-o", "--output", help="Output PNG path", default=None)
    parser.add_argument("-t", "--title", help="Plot title", default=None)
    args = parser.parse_args()

    # Interactive prompt if user didn't pass country via CLI and is in an interactive shell
    country = args.country
    if country is None:
        try:
            user_input = input("Enter Country Code (e.g. ID for Indonesia, or press Enter for Global): ").strip()
            country = user_input.upper() if user_input else "GLOBAL"
        except (EOFError, KeyboardInterrupt):
            country = "GLOBAL"
    else:
        country = country.upper()

    caida_default = "20260901.as-rel2.txt"
    if args.input is None and os.path.exists(caida_default):
        args.input = caida_default

    output_filename = args.output
    if output_filename is None:
        output_filename = f"as_core_{country.lower()}.png" if country != "GLOBAL" else "as_core_global.png"

    plot_title = args.title
    if plot_title is None:
        plot_title = f"{country} IPv4 AS Core Topology" if country != "GLOBAL" else "CAIDA IPv4 AS Core Topology"

    if country != "GLOBAL":
        nodes, edges = build_country_topology(args.input, country_code=country, top_n=args.top)
    else:
        if args.input and os.path.exists(args.input):
            from as_core import build_topology_from_caida
            nodes, edges = build_topology_from_caida(args.input, top_n=args.top)
        else:
            from as_core import generate_sample_2020_topology
            nodes, edges = generate_sample_2020_topology(num_stubs=400)

    print(f"[+] Rendering AS Core visualization to {output_filename}...")
    render_as_core(nodes, edges, output_path=output_filename, dpi=300, title=plot_title, country=country)
    print(f"[✓] Visualization successfully saved to {output_filename}")


if __name__ == "__main__":
    main()
