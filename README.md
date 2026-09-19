# CAIDA IPv4 AS Core Visualizer

A Python implementation replicating CAIDA's macroscopic Internet topology visualization, specifically modeled after the **[CAIDA IPv4 AS Core 2020](https://www.caida.org/projects/as-core/2020/)** graph.

---

## 1. How the Script Works

The visualization maps each Autonomous System (AS) onto a 2D **polar coordinate system $(r, \theta)$**, which is then converted into Cartesian coordinates $(x, y)$ for rendering.

```
                    [ 90° / +E (Asia / APNIC) ]
                                 ▲
                                 │
 [ 180° / Dateline ] ◄─────── (0, 0) ───────► [ 0° / Greenwich (Europe / RIPE) ]
                               Core
                                 │
                                 ▼
                 [ -90° / -W (Americas / ARIN) ]
```

### A. Radial Coordinate ($r$): Hierarchy & Centrality
The radial distance from the center $(0, 0)$ is determined by the **Customer Cone size** (the total number of ASes reachable through an AS's customer routes):

$$
r = 1 - \frac{\log(\text{Customer Cone Size} + 1)}{\log(\max(\text{Customer Cone Size}) + 1)}
$$

* **Deep Core ($r \approx 0$):** Global Tier-1 transit providers (e.g., Lumen/Level3 AS3356, Cogent AS174, Arelion AS1299, NTT AS2914, Hurricane Electric AS6939) have massive customer cones ($>30,000$ ASes) and sit near the center.
* **Periphery ($r \approx 1$):** Stub networks and enterprise edge ASes with customer cone of 0 are plotted at the outer circle.

### B. Angular Coordinate ($\theta$): Geographic Longitude
The angle $\theta$ corresponds to the geographic longitude of the AS:

$$
\theta = \lambda \cdot \frac{\pi}{180^{\circ}} \quad (\lambda \in [-180^{\circ}, +180^{\circ}])
$$

* **Longitude Centroid:** The geographic coordinates of each AS are computed as the weighted centroid of the IP prefixes announced by that AS.
* This arranges ASes into distinct geographic clusters around the circle:
  * **ARIN (North America):** ~$-125^\circ$ to $-65^\circ$
  * **LACNIC (Latin America):** ~$-80^\circ$ to $-35^\circ$
  * **RIPE (Europe / Middle East):** ~$-10^\circ$ to $+45^\circ$
  * **AFRINIC (Africa):** ~$10^\circ$ to $40^\circ$
  * **APNIC (Asia-Pacific):** ~$60^\circ$ to $150^\circ$

### C. Link Curvature (Quadratic Bézier Curves)
Instead of straight lines (which create visual clutter), peering and transit links between two points $P_1(x_1, y_1)$ and $P_2(x_2, y_2)$ are rendered using quadratic Bézier curves with a control point $C(x_c, y_c)$ pulled inward toward the origin:

$$
C = k \cdot (P_1 + P_2) \quad (\text{where bend factor } k \approx 0.32)
$$

$$
B(t) = (1 - t)^2 P_1 + 2(1 - t)t C + t^2 P_2 \quad (t \in [0, 1])
$$

Links connecting deep core ASes are drawn with higher opacity, while links to edge stubs are softly faded.

---

## 2. How to Obtain Datasets from CAIDA

To reproduce the exact **2020** graph using real CAIDA data, download the following datasets from CAIDA's public data repositories:

### A. AS Relationships & Customer Cones
* **Dataset:** CAIDA AS Relationships (`serial-2`)
* **URL:** [https://publicdata.caida.org/datasets/as-relationships/serial-2/](https://publicdata.caida.org/datasets/as-relationships/serial-2/)
* **2020 File Example:** `20200101.as-rel2.txt.bz2`
* **Format:**
  ```text
  <provider-as>|<customer-as>|-1|<source>   # Provider-to-Customer link
  <peer-as>|<peer-as>|0|<source>            # Peer-to-Peer link
  ```

### B. AS Rank API (Direct Query)
CAIDA provides a GraphQL API to retrieve customer cone sizes, ranks, and organization details directly:
* **API Endpoint:** `https://api.asrank.caida.org/v2/graphql`
* **Example Query:**
  ```graphql
  {
    asns(first: 500, sort: "-cone_size") {
      edges {
        node {
          asn
          asnName
          rank
          cone {
            asnsCount
          }
          country {
            id
            name
          }
          rir {
            name
          }
        }
      }
    }
  }
  ```

### C. AS-to-Organization (AS2Org) Mapping
* **Dataset:** CAIDA AS Organizations
* **URL:** [https://publicdata.caida.org/datasets/as-organizations/](https://publicdata.caida.org/datasets/as-organizations/)
* **2020 File Example:** `20200101.as-org2info.txt.gz`
* Maps each ASN to its legal organization name, country, and managing RIR.

### D. Prefix-to-AS & Geolocation (pfx2as + GeoIP)
* **Dataset:** RouteViews Prefix-to-AS mapping
* **URL:** [https://publicdata.caida.org/datasets/routing/routeviews-prefix2as/](https://publicdata.caida.org/datasets/routing/routeviews-prefix2as/)
* **GeoIP Mapping:** Cross-reference prefixes with [MaxMind GeoLite2 2020](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) or IP2Location to derive the weighted average longitude per AS.

---

## 3. Project Structure

* **[`as_core.py`](file:///Users/dikshie/VIRTUAL/draw_as_core/as_core.py)**: Main IPv4 AS Core module containing polar coordinate calculations, Bézier edge generation, sample topology generator, and rendering pipeline.
* **[`as_core_IPv6.py`](file:///Users/dikshie/VIRTUAL/draw_as_core/as_core_IPv6.py)**: IPv6 AS Core module tailored for IPv6 routing topologies, customer cones, and dominant IPv6 backbones (e.g., Hurricane Electric AS6939).
* **[`test_as_core.py`](file:///Users/dikshie/VIRTUAL/draw_as_core/test_as_core.py)**: Unit tests for IPv4 pipeline.
* **[`test_as_core_IPv6.py`](file:///Users/dikshie/VIRTUAL/draw_as_core/test_as_core_IPv6.py)**: Unit tests for IPv6 pipeline.
* **[`as_core_2020.png`](file:///Users/dikshie/VIRTUAL/draw_as_core/as_core_2020.png)**: Rendered 300 DPI visualization output.

---

## 4. Setup & Running

### Requirements
* Python 3.10+
* `matplotlib`
* `numpy`
* `pytest`

### Running Unit Tests
```bash
# Run all IPv4 and IPv6 unit tests:
pytest -v test_as_core.py test_as_core_IPv6.py
```

### Generating Visualizations

#### IPv4 AS Core:
```bash
# 1. Global IPv4 AS Core visualization:
python as_core.py -i 20260901.as-rel2.txt -n 800 -o as_core_2026.png

# 2. Country-specific IPv4 AS Core (e.g. Indonesia - ID):
python as_core.py -i 20260901.as-rel2.txt -c ID -o as_core_id.png

# 3. Highlight specific institutions / ASNs (e.g. ITB, IDREN, Indosat, XL Axiata, APJII, Telkom):
python as_core.py -i 20260901.as-rel2.txt -c ID -s 4796,64302,4761,24203,7597,7713 -o as_core_id.png
```

#### IPv6 AS Core:
```bash
# 1. Global IPv6 AS Core visualization (featuring HE AS6939 as #1 core):
python as_core_IPv6.py -c GLOBAL -o as_core_ipv6_global.png

# 2. Country-specific IPv6 AS Core (e.g. Indonesia - ID):
python as_core_IPv6.py -i 20260901.as-rel2.txt -c ID -o as_core_ipv6_id.png

# 3. Highlight specific IPv6 institutions / ASNs:
python as_core_IPv6.py -c ID -s 4796,64302,4761,24203,7597,7713 -o as_core_ipv6_id.png
```

---

## 5. Empirical Findings (CAIDA 2026-09-01 Snapshot)

Processing the real-world CAIDA dataset (`20260901.as-rel2.txt`) through the customer cone computation engine yielded the following macroscopic insights into the global IPv4 routing topology:

### Macro Topology Metrics
| Metric | Value | Description |
| :--- | :--- | :--- |
| **Total Analyzed ASes** | **80,514** | Active Autonomous Systems in global BGP routing tables |
| **Total AS Relationships** | **674,158** | Provider-to-Customer (`-1`) and Peer-to-Peer (`0`) links |
| **Transit Providers** | **12,839** (15.9%) | ASes providing upstream transit (Customer Cone $> 0$) |
| **Edge / Stub ASes** | **67,675** (84.1%) | End-user, enterprise, and access networks at the perimeter |
| **Computation Time** | **~3.1 seconds** | Full transitive DAG traversal across all 80k+ ASes |

### Top 10 Core Providers by Customer Cone Reachability
The top Tier-1 backbones form the dense center of the polar visualization:

| Rank | ASN | Organization | RIR | Customer Cone (ASes) | Global Reach % |
| :---: | :---: | :--- | :---: | :---: | :---: |
| 1 | **AS3356** | Lumen / Level 3 | ARIN | 73,668 | 91.5% |
| 2 | **AS1299** | Arelion (formerly Telia) | RIPE | 71,365 | 88.6% |
| 3 | **AS174** | Cogent Communications | ARIN | 71,047 | 88.2% |
| 4 | **AS3257** | GTT Communications | ARIN | 67,072 | 83.3% |
| 5 | **AS2914** | NTT Communications | APNIC | 66,606 | 82.7% |
| 6 | **AS701** | Verizon (MCI / UUNET) | ARIN | 60,472 | 75.1% |
| 7 | **AS6453** | Tata Communications | APNIC | 60,006 | 74.5% |
| 8 | **AS5511** | Orange | RIPE | 59,464 | 73.9% |
| 9 | **AS6762** | Telecom Italia Sparkle | RIPE | 58,589 | 72.8% |
| 10 | **AS6461** | Zayo Bandwidth | ARIN | 58,357 | 72.5% |

### Key Structural Observations
1. **Extreme Power-Law Centrality:** Fewer than 20 global Tier-1 backbones provide transitive reachability to over 80% of the entire Internet.
2. **Dense Regional Mesh:** High peering density exists between North American (ARIN) and European (RIPE) backbones, while Latin America (LACNIC) and Africa (AFRINIC) rely heavily on transatlantic and transpacific Tier-1 gateways (e.g., SEACOM, Telecom Brasil, Liquid Telecom).
3. **Hyperscaler Flattening:** Major CDNs and hyperscalers (Google AS15169, Cloudflare AS13335, AWS AS16509, Akamai AS20940) peer extensively with hundreds of Tier-1/Tier-2 backbones, positioning them prominently near the inner rings despite functioning primarily as content originators rather than transit sellers.

---

## 6. Country AS Core Case Study: Indonesia (`ID`)

Using the country filter (`-c ID`), the visualizer extracts domestic Indonesian Autonomous Systems and their interconnects:

### Indonesia Topology Highlights
* **Active Indonesian ASes in Graph:** **711 ASes** (out of ~3,900 APNIC delegations)
* **Domestic Interconnect Links:** **2,029 active BGP peering and transit relationships**
* **Prominently Highlighted Networks:**
  * **AS7713 (Telkom Indonesia):** Deep national core backbone ($r = 0.000$, center). Largest domestic customer cone.
  * **AS4761 (Indosat Ooredoo Hutchison):** Major national mobile & enterprise transit provider ($r = 0.073$, core ring).
  * **AS24203 (XL Axiata):** Major national telecommunications provider ($r = 0.187$, core ring).
  * **AS64302 (IDREN - Indonesia Research and Education Network):** National academic & research network ($r = 0.690$, Java sector / $107.2^\circ$E), connecting Indonesian universities including ITB.
  * **AS7597 (APJII / IIX - Indonesia Internet Exchange):** Primary national Internet exchange point ($r = 0.936$, Java sector).
  * **AS4796 (ITB - Institut Teknologi Bandung):** Premier higher education & research institute ($r = 1.000$, Java sector / Bandung $107.6^\circ$E).
* **Anti-Collision Callout Engine:**
  * Core nodes ($r < 0.35$) use dedicated radial orbit callout pins to prevent overlapping in dense inner rings.
  * Outer edge nodes ($r \ge 0.35$) use angular-sorted, staggered radial pointers ($r = 1.08$ to $1.16$) with background callout cards to ensure labels like APJII, IDREN, and ITB remain crisp and readable without overlapping.
* **Geographic Island Sectors:**
  * **Java (Red):** Dominates domestic transit volume and exchange interconnects (Jakarta, Bandung, Surabaya).
  * **Sumatra (Blue):** Batam and Medan gateway connectivity.
  * **Kalimantan (Green), Bali & Nusa Tenggara (Amber), Sulawesi (Purple), Maluku & Papua (Pink):** Regional distribution clusters connected to the Java transit core.



