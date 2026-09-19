# Determining ASN Longitude Coordinates (Global & Indonesia Case Study)

In Internet topology mapping and CAIDA-style polar visualizations, an Autonomous System (ASN) is not a single physical point on Earth, but a logical administrative domain that routes multiple IP address prefixes across cities, islands, and continents.

This document outlines the standard methodology used by CAIDA and Internet measurement researchers to derive the **geographic longitude ($\theta$)** of an Autonomous System, with specific application to **Indonesia (`ID`)**.

---

## 1. The Prefix-Weighted Centroid Methodology

CAIDA derives the geographic position of an AS through a 3-step pipeline:

```
┌─────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│ 1. BGP Prefix-to-AS     │ ──► │ 2. IP Geolocation DB   │ ──► │ 3. Weighted Centroid   │
│ (RouteViews / pfx2as)   │     │ (MaxMind / NetAcuity)  │     │ Calculation            │
│ AS7713 owns:            │     │ 180.240.0.0/13 -> JKT  │     │ Weighted by /24 block  │
│ - 180.240.0.0/13        │     │ (Lon: 106.8°E)         │     │ count across islands   │
│ - 118.96.0.0/12         │     │ 125.160.0.0/11 -> SBY  │     │                        │
└─────────────────────────┘     └────────────────────────┘     └────────────────────────┘
```

### Step 1: BGP Prefix Extraction (`pfx2as`)
Collect all IPv4 prefixes originated by the ASN from global BGP routing tables:
* **Dataset:** [CAIDA RouteViews Prefix-to-AS](https://publicdata.caida.org/datasets/routing/routeviews-prefix2as/) or RIPE RIS.
* *Example:* **AS131759** (Batam Bintan Telekomunikasi) originates `103.24.56.0/22`, `103.111.16.0/23`, etc.

### Step 2: Prefix Geocoding
Map each originated prefix to geographic coordinates $(\text{Latitude}_i, \text{Longitude}_i)$ using:
* **MaxMind GeoLite2-City / GeoIP2**
* **Digital Element NetAcuity** (CAIDA default)
* **IP2Location**
* **APNIC / RIPE WHOIS & RDAP Records** (Organization registration address)
* **PeeringDB Facilities** (Coordinates of Internet Exchange Points and Data Centers where the ASN maintains physical presence)

### Step 3: Weighted Centroid Computation
Calculate the average longitude weighted by the address pool size of each prefix ($N_i = 2^{32 - \text{prefix\_length}}$):

$$
\text{Longitude}_{\text{ASN}} = \frac{\sum_{i=1}^{k} \left( N_i \times \text{Longitude}_i \right)}{\sum_{i=1}^{k} N_i}
$$

For multi-homed national transit providers (e.g., Telkom Indonesia AS7713), this naturally places the centroid at the primary traffic concentration hub (Jakarta / Cyber 1 / IDC Duren Tiga).

---

## 2. Geographic Longitude Reference for Indonesia

Indonesia spans **$95.0^\circ\text{E}$ (Sabang, Aceh)** to **$141.0^\circ\text{E}$ (Merauke, Papua)**. In country-specific visualizations, longitudes are mapped across regional island sectors:

| Island / Region | Longitude Span ($\lambda$) | Major Hubs / Cities | Example ASNs & Coordinates |
| :--- | :---: | :--- | :--- |
| **Sumatra** | $95.0^\circ\text{E} - 105.0^\circ\text{E}$ | Medan ($98.6^\circ\text{E}$), Batam ($104.0^\circ\text{E}$), Palembang ($104.7^\circ\text{E}$) | **AS131759** (Batam Bintan Telko) $\to 104.0^\circ\text{E}$ |
| **Java** | $106.0^\circ\text{E} - 114.5^\circ\text{E}$ | Jakarta ($106.8^\circ\text{E}$), Bandung ($107.6^\circ\text{E}$), Surabaya ($112.7^\circ\text{E}$) | **AS7713** (Telkom), **AS4761** (Indosat), **AS17451** (Biznet) $\to 106.8^\circ\text{E}$ |
| **Kalimantan** | $108.5^\circ\text{E} - 117.5^\circ\text{E}$ | Pontianak ($109.3^\circ\text{E}$), Balikpapan ($116.8^\circ\text{E}$), Banjarmasin ($114.6^\circ\text{E}$) | **AS136050** (Kalimantan Net) $\to 114.6^\circ\text{E}$ |
| **Bali & Nusa Tenggara** | $114.5^\circ\text{E} - 125.0^\circ\text{E}$ | Denpasar ($115.2^\circ\text{E}$), Mataram ($116.1^\circ\text{E}$), Kupang ($123.6^\circ\text{E}$) | **AS133481** (Bali Fiber) $\to 115.2^\circ\text{E}$ |
| **Sulawesi** | $118.5^\circ\text{E} - 125.5^\circ\text{E}$ | Makassar ($119.4^\circ\text{E}$), Manado ($124.8^\circ\text{E}$) | **AS136052** (Makassar Cyber) $\to 119.4^\circ\text{E}$ |
| **Maluku & Papua** | $126.0^\circ\text{E} - 141.0^\circ\text{E}$ | Ambon ($128.1^\circ\text{E}$), Jayapura ($140.7^\circ\text{E}$), Merauke ($140.4^\circ\text{E}$) | **AS138382** (Papua Digital Net) $\to 140.7^\circ\text{E}$ |

---

## 3. Practical APIs to Query Indonesian ASN Longitudes

### A. RIPEstat Geolocation API (Free, No Auth)
Query the geolocated centroid for any ASN directly:
```bash
curl -s "https://stat.ripe.net/data/geoloc/data.json?resource=AS7713" | jq '.data.locations[0]'
```
*Sample JSON Response:*
```json
{
  "country": "ID",
  "city": "Jakarta",
  "latitude": -6.2146,
  "longitude": 106.8451
}
```

### B. PeeringDB API (Free, Data Center Coordinates)
Find data center presence and IXP coordinates for an ASN:
```bash
curl -s "https://www.peeringdb.com/api/net?asn=7713" | jq '.data[0] | {name, city, country, website}'
```

### C. Automated Python Prefix Centroid Script
```python
import requests
import geoip2.database

def get_asn_longitude_centroid(asn: int, geoip_db_path: str = "GeoLite2-City.mmdb") -> float:
    """Calculates the prefix-weighted longitude centroid for an ASN."""
    url = f"https://stat.ripe.net/data/announced-prefixes/data.json?resource=AS{asn}"
    resp = requests.get(url, timeout=10).json()
    prefixes = resp.get("data", {}).get("prefixes", [])

    if not prefixes:
        return 106.8  # Fallback to Jakarta centroid

    reader = geoip2.database.Reader(geoip_db_path)
    total_ips = 0
    weighted_lon_sum = 0.0

    for item in prefixes:
        prefix = item["prefix"]
        ip, prefix_len = prefix.split("/")
        num_ips = 2 ** (32 - int(prefix_len))
        try:
            loc = reader.city(ip).location
            if loc.longitude is not None:
                weighted_lon_sum += loc.longitude * num_ips
                total_ips += num_ips
        except Exception:
            continue

    reader.close()
    return (weighted_lon_sum / total_ips) if total_ips > 0 else 106.8
```
