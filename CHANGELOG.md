# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-10-27

### Changed
- **Unified Shared Core Architecture**: Consolidated shared data structures (`ASNode`), palettes (`RIR_PALETTE`, `ID_SECTOR_PALETTE`), coordinate geometry, CAIDA dataset parsing, and rendering logic into `as_core.py`, removing ~730 lines of duplicate code from `as_core_IPv6.py`.
- **$O(|V| + |E|)$ Country Filtering**: Replaced $O(|V| \cdot |E|)$ linear edge scanning in `build_country_topology` with set intersection over precomputed active edge ASNs.
- **Memoized Customer Cone Calculation**: Added subtree memoization and cycle protection (`visited.discard(provider)`) in `compute_customer_cones`.
- **Deterministic ASN Hashing & Local RNG**: Replaced non-deterministic `hash(str(asn))` with `zlib.crc32` (`_asn_seed`) and replaced global `np.random.seed(42)` calls with isolated `np.random.default_rng(42)` instances.
- **Aligned Indonesia Sector Angles**: Updated Indonesia sector axes in `render_as_core` to use `calculate_angle(..., country="ID")` at each island's representative longitude so radial guide lines align with projected node positions.

### Fixed
- **Non-ID Country Simulation Fallback**: Added hub-and-spoke simulation fallback when running `build_country_topology` without a CAIDA input file for non-Indonesian country codes.
- **IPv6 Dataset Auto-Detection**: Removed silent fallback to the IPv4 dataset (`20260901.as-rel2.txt`) in `as_core_IPv6.py:main`.
- **Matplotlib Figure Memory Management**: Added `plt.close(fig)` after saving in `render_as_core` to prevent memory leaks during batch or test runs.
- **Offline Test Suite & Expanded Coverage**: Isolated unit tests from live RIR network calls using temporary cache directories (`cache_dir`) and added test coverage for `.bz2`/`.gz` archives, `build_topology_from_caida`, cyclic graphs, `parse_highlight_asns`, and CLI `main()` execution.

## [0.1.0] - 2026-10-20

### Added
- **IPv4 AS Core Visualizer**: Macroscopic Internet topology and CAIDA-style AS Core visualization in polar coordinates (`as_core.py`).
- **IPv6 AS Core Visualizer**: Dedicated IPv6 Internet topology visualization engine (`as_core_IPv6.py`).
- **CAIDA Data Processing**: BZ2/raw CAIDA AS Relationships (`as-rel2`) parser and customer cone BFS graph calculation engine.
- **Country-Level Filtering & Interactive Mode**: Filter topologies by country code (with detailed Indonesian case study / ID network topology).
- **Indonesian Core Highlights**: Dedicated coordinates, rank calculations, and highlighting for prominent Indonesian ASNs including OpenIXP (AS7717), IDREN (AS64302), ITB (AS4791), Telkom (AS7713), Indosat (AS4761), XL Axiata (AS24203), and APJII (AS23947).
- **Anti-Overlap Radial Callouts**: Radial callout algorithm with dynamic pointer lines to prevent label collisions at the dense center core.
- **Automated Testing**: Comprehensive test suites for IPv4 (`test_as_core.py`) and IPv6 (`test_as_core_IPv6.py`) using `pytest`.
- **CI/CD Pipeline**: GitHub Actions workflow testing Python 3.10 through 3.13 using `uv`, Ruff linter/formatter, and pytest.
- **Developer Tooling**: Added `Makefile` shortcuts and pre-commit hooks (`.pre-commit-config.yaml`) for formatting and linting.
- **Documentation**: Comprehensive methodology guide on ASN longitude determination and geographic positioning (`LONGITUDE.md`).

### Changed
- Configured and enforced Ruff linting and formatting standards (`pyproject.toml`).
- Enhanced `README.md` with status badges, CI/CD references, and visualization gallery.
- Upgraded CI actions to Node 24 on `ubuntu-24.04` with `uv` lockfile dependency caching.

### Fixed
- Resolved core label overlaps in dense cluster rings using radial offset geometry.
- Standardized mathematical equations in `README.md` for KaTeX/MathJax and GitHub rendering.
