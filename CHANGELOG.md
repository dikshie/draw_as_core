# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
