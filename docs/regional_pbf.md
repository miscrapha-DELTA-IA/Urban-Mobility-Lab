# Alternative offline importer: Geofabrik Nordeste -> Parnaiba SUMO

## Why this exists

On 2026-11-05 the Windows user confirmed 30 local tests passing and Eclipse SUMO 1.28.0 detected. The Overpass import still received HTTP 504 at the FIRST of eight road-only tiles. This is an external service failure. Avoid hammering Overpass; use a regional dated extract instead.

Official sources:
- https://download.geofabrik.de/south-america/brazil/nordeste.html
- https://download.geofabrik.de/south-america/brazil/nordeste-261103.osm.pbf
- https://download.geofabrik.de/south-america/brazil/nordeste-261103.osm.pbf.md5

The file is the dated 2026-11-03 regional snapshot, approximately 424 MB. It covers all Nordeste, not just Parnaiba; the project extracts Parnaiba locally without Overpass. The pinned filename is more scientifically reproducible than latest.

## 1. Download two dated files using Windows PowerShell 5.1

~~~powershell
Set-Location "$env:USERPROFILE\Downloads\Urban-Mobility-Lab"
$python = ".\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Force "data\raw\osm" | Out-Null

# Resume if supported by the server; do not replace completed files casually.
curl.exe --fail --location --continue-at - --retry 2 `
  --output "data\raw\osm\nordeste-261103.osm.pbf" `
  "https://download.geofabrik.de/south-america/brazil/nordeste-261103.osm.pbf"
if ($LASTEXITCODE -ne 0) { throw "Falha no download PBF." }

curl.exe --fail --location --retry 2 `
  --output "data\raw\osm\nordeste-261103.osm.pbf.md5" `
  "https://download.geofabrik.de/south-america/brazil/nordeste-261103.osm.pbf.md5"
if ($LASTEXITCODE -ne 0) { throw "Falha no checksum MD5." }
~~~

Note: curl --continue-at is only reliable when the server supports HTTP range requests. The checksum gate always decides whether the PBF is safe to use.

## 2. Install the local PBF parser

Python 3.11 Windows wheels for osmium 4.3.2 are published on PyPI, so there is no need for a C++ compiler on that platform.

~~~powershell
& $python -m pip install --no-cache-dir --only-binary=:all: osmium==4.3.2
if ($LASTEXITCODE -ne 0) { throw "Pyosmium nao instalado." }
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Testes falharam." }
~~~

## 3. Validate, extract and convert without Overpass

~~~powershell
& $python -m urban_mobility_lab.regional_pbf plan
if ($LASTEXITCODE -ne 0) { throw "Plano invalido." }

& $python -m urban_mobility_lab.regional_pbf verify
if ($LASTEXITCODE -ne 0) { throw "PBF falhou no MD5 oficial." }

& $python -m urban_mobility_lab.regional_pbf extract
if ($LASTEXITCODE -ne 0) { throw "Recorte local nao concluido." }

& $python -m urban_mobility_lab.regional_pbf convert
if ($LASTEXITCODE -ne 0) { throw "Conversao SUMO falhou." }

& $python -m urban_mobility_lab.regional_pbf inspect
if ($LASTEXITCODE -ne 0) { throw "Inspecao SUMO falhou." }

& "C:\Program Files (x86)\SUMO\bin\sumo-gui.exe" `
  -n "data\sumo\parnaiba_geofabrik_20261103.net.xml"
~~~

The regional importer reads the same dated PBF four times: it locates nodes inside the bounding rectangle of the original GraphML; finds highway ways touching those nodes; includes all nodes referenced by selected ways; preserves only fully referenced turn restriction relations; and writes XML only after integrity checks. The road network XML is then passed to SUMO netconvert using a temporary candidate file. No source road GraphML is altered.

Generated artifacts:
- data/raw/osm/parnaiba_geofabrik_20261103.osm.xml
- reports/parnaiba_regional_plan.json
- reports/parnaiba_regional_import.json
- data/sumo/parnaiba_geofabrik_20261103.net.xml

## Scientific caveats

The input rectangular bbox can include places outside the actual municipality boundary. Road ways crossing it without vertices inside may be omitted. Incomplete relation-based turn restrictions are omitted and counted. Not all road traffic rules, lane counts or real signal phases are validated. This is a new OSM data version and is not identical to the graph extracted earlier; both snapshots must be reconciled spatially before drawing comparisons. A SUMO network file alone is not a simulated traffic flow. No measured traffic is included.

## Checklist

- [ ] Geofabrik PBF plus sidecar MD5 downloaded, verified
- [ ] Local extraction generated OSM XML and checked way-node completeness
- [ ] Regional SUMO network created and loaded in sumo-gui
- [ ] Geographic coverage compared against 6585-node municipal OSMnx reference
- [ ] Signal, turn, and junction restrictions reviewed
- [ ] Synthetic demand generated and separately validated in SUMO
- [ ] Independent field calibration in MIRANTE-01
