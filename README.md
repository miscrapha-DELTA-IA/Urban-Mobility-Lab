# Urban Mobility Lab

**Reproducible research framework for urban mobility digital twins.**

Urban Mobility Lab develops open, inspectable methods for road-network reconstruction, traffic simulation, geospatial analysis and, eventually, calibrated machine-learning models. The first case study is **Parnaíba, Piauí, Brazil**.

> **Research status:** early scientific prototype. No real traffic counts or validated forecasts are shipped. A road map is not a live traffic measurement. The present repository has no effective software license yet; public visibility alone does not grant reuse rights.

## Scope and scientific boundaries

- Import directed, drivable OpenStreetMap road networks using OSMnx.
- Inspect topology and create reproducible, time-stamped metadata.
- Build synthetic traffic-demand scenarios for Eclipse SUMO (future milestone).
- Calibrate and test a traffic digital twin using **independently observed** counts and signal phases (future milestone).
- Explore mobility, safety and wellbeing research without claiming causal effects from observational correlation.

## Quick start (Windows / PowerShell)

```powershell
git clone https://github.com/miscrapha-DELTA-IA/Urban-Mobility-Lab.git
cd Urban-Mobility-Lab
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m urban_mobility_lab.ingestion --place "Parnaíba, Piauí, Brazil"
```

The final command **requires internet access** to resolve the municipal boundary and download map features. Its outputs are:
- `data/networks/parnaiba_drive.graphml`: the directed road graph;
- `data/networks/parnaiba_drive.metadata.json`: provenance, basic topology metrics and timestamp.

The administrative boundary returned by a geocoder can cover rural and coastal areas. **Review and document the urban study boundary before claiming full urban coverage.** Map speed limits, turn restrictions, traffic-signal metadata, and road connectivity also require field or authoritative checks.

## Scientific workflow

1. Define outcomes and a validation protocol: [research/research_protocol.md](research/research_protocol.md).
2. Reconstruct and quality-check the road graph with [src/urban_mobility_lab/ingestion.py](src/urban_mobility_lab/ingestion.py). The **first full-city study uses the entire existing municipality road graph, without clipping**: see [full-city scope](docs/full_city_scope.md). The [AOI editor](docs/urban_aoi.md) remains available for subareas such as MIRANTE-01.
3. Build reproducible SUMO demand scenarios ([scenarios](scenarios/README.md), **not implemented yet**).
4. Obtain independent field observations, starting with [MIRANTE-01](stations/MIRANTE-01.md).
5. Hold out observation periods and compare simulation outputs to reality using the common [data dictionary](research/data_dictionary.md).

See [roadmap](docs/roadmap.md) for a truthful implementation checklist.

## Tests

```powershell
python -m pytest -q
```

Unit tests intentionally use synthetic graphs and do not contact map services. Downloading the Parnaíba road network is a separate **integration step**, not part of CI.

## Data governance

Keep raw recordings, personal data and large processed files outside Git. Publish only data that can legally and ethically be shared. OpenStreetMap material has its own attribution and ODbL obligations. The observational sensor pilot must avoid identifying drivers, passengers, plates or faces.

## Planned technology

Python 3.11+, OSMnx, NetworkX, pytest; later SUMO, GeoPandas/PostGIS, ML frameworks, and a geospatial web frontend.

## License

The existing `License` file is empty. A license must be chosen and added before presenting the code as freely reusable under a specific open-source license.
