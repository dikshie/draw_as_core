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

* **[`as_core.py`](file:///Users/dikshie/VIRTUAL/draw_as_core/as_core.py)**: Main module containing the polar coordinate calculations, Bézier edge generation, sample topology generator, and high-resolution rendering pipeline.
* **[`test_as_core.py`](file:///Users/dikshie/VIRTUAL/draw_as_core/test_as_core.py)**: Unit tests verifying boundary math, monotonicity, geometry, and rendering pipeline.
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
pytest -v test_as_core.py
```

### Generating the Visualization
```bash
python as_core.py
```
This produces `as_core_2020.png` in the current working directory.
