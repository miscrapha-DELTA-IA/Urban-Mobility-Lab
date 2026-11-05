# Parnaíba urban-core AOI: reproducible crop

**Status:** software prepared; the study-area polygon is not yet selected or validated.

A manual polygon is safer than inventing coordinates for the built-up core. This workflow **reuses the 6,585-node municipal GraphML already downloaded** and does not overwrite it.

## 1 — Open interactive area editor (Windows PowerShell 5.1)

From the project root:

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e ".[dev,viz,ui]"
& $python -m pytest -q
& $python -m urban_mobility_lab.roi editor
Start-Process "reports\parnaiba_aoi_editor.html"
```

The editor is a local HTML page. Its **basemap and drawing scripts require internet access** when you open it. It displays streets, not real-time traffic, and does not automatically save your selected area into the repository.

On the map:
1. Zoom into the main urban area of Parnaíba.
2. Use the left-hand drawing toolbar to draw **one** polygon (or rectangle).
3. Include Mirante, the major adjacent intersections and the roads connecting them; do not trim the traffic approaches too tightly.
4. Use **Export** at the upper-right to download `parnaiba_urban_core.geojson`.
5. Review the shape and move it to `research/aoi/parnaiba_urban_core.geojson`.

A polygon/rectangle selection does not establish the official built-up-area boundary; it is an **initial research AOI** to be reviewed.

## 2 — Crop the existing road graph

```powershell
New-Item -ItemType Directory -Force "research\aoi" | Out-Null
Copy-Item -LiteralPath "$env:USERPROFILE\Downloads\parnaiba_urban_core.geojson" `
    -Destination "research\aoi\parnaiba_urban_core.geojson" -Force

& $python -m urban_mobility_lab.roi clip
```

If the browser added a suffix to the download name, adjust the source path.

Outputs:
- `data/networks/parnaiba_urban_core.graphml`: cropped directed graph;
- `reports/parnaiba_urban_core_audit.json`: topology audit, input SHA-256 hashes, AOI bounds and geodesic area.

The source `data/networks/parnaiba_drive.graphml` stays **unchanged**.

By default, nodes immediately beyond the boundary may be retained to preserve a crossing road's last connection (`truncate_by_edge=True`). **The network edge geometries are not physically split at the polygon.** Use `--strict-boundary` to omit all nodes outside the AOI. Use `--largest-component-only` only after examining disconnected segments; neither option is silently applied.

## 3 — Review the cropped PNG and audit

```powershell
& $python -m urban_mobility_lab.audit `
    --input "data/networks/parnaiba_urban_core.graphml" `
    --output "reports/parnaiba_urban_review.json" `
    --plot `
    --map-output "reports/parnaiba_urban_review.png"

Start-Process "reports\parnaiba_urban_review.png"
```

This outputs a **road-network map**, not estimated traffic volumes. Inspect the edges of the AOI for severed roads and artificial dead ends. Check the location of Mirante on the map rather than relying on an unverified geocoding result. Review directions, intersections, access roads and OSM completeness before SUMO conversion.

## Approval criteria before SUMO

- [ ] AOI boundaries visually reviewed with Mirante and approach roads included;
- [ ] AOI GeoJSON and provenance hashes retained, inputs version-controlled appropriately;
- [ ] Cropped network audit reports no invalid lengths/coordinates;
- [ ] Disconnected components and boundary effects reviewed;
- [ ] Restrictions, lanes and signals marked as unverified pending field checks;
- [ ] Distinguish mapped topology, simulated demand and independent traffic counts.

**Scientific disclaimer:** This process builds only a candidate computational road network. It does not validate traffic flow, accident risk, real-world travel time or causal effects.
