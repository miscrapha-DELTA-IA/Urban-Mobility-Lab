# Parnaíba urban-core AOI: reproducible crop

**Status:** software prepared; the study-area polygon is not yet selected or validated.

A manual polygon is safer than inventing coordinates for the built-up core. This workflow **reuses the 6,585-node municipal GraphML already downloaded** and does not overwrite it.

## 1 — Open interactive area editor (Windows PowerShell 5.1)

From the project root:

```powershell
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -e ".[dev,viz]"
& $python -m pytest -q
& $python -m urban_mobility_lab.roi editor
Start-Process "reports\parnaiba_aoi_editor.html"
```

The editor is a self-contained local HTML page with the OSM roads embedded from GraphML. It does **not** use Folium, external image tiles, or JavaScript dependencies. The road geometry, panning/zooming, selection and GeoJSON export work completely offline. An optional **Conferir no OSM** hyperlink opens the current view on the external site only when clicked. The editor itself makes no external requests.

If an earlier Folium installation failed with Windows `[Errno 22] Invalid argument`, **do not reinstall it**: simply pull the revised branch and run `python -m urban_mobility_lab.roi editor`. The generated HTML does not require a local server.

On the map:
1. Zoom into the main urban area of Parnaíba using the mouse wheel; drag to pan.
2. Click **Desenhar polígono**, mark at least three points **in geographical perimeter order (clockwise or counterclockwise)**, then click **Concluir**. The editor rejects crossing edges and invalid polygon closure; use **Desfazer ponto** to correct your route. Do not zigzag across the city.
3. Include Mirante, the major adjacent intersections and the roads connecting them; do not trim the traffic approaches too tightly. The **Conferir no OSM** link opens the matching map location for reference.
4. Click **Exportar GeoJSON** to download `parnaiba_urban_core.geojson`.
5. Review the polygon and copy it to `research/aoi/parnaiba_urban_core.geojson`.

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

## Windows HTTP 403 tile errors (legacy HTML)

The earlier editor requested images directly from the OpenStreetMap public tile server and some Windows/browser environments received HTTP 403 images. The current editor **does not request any tiles**. After pulling the updated branch, regenerate the HTML with `python -m urban_mobility_lab.roi editor` and reopen the regenerated local file. Do not reuse the old tab or HTML. The scientific GraphML is unchanged.

## Quality gate: invalid manual polygon

The first GeoJSON submitted for review on 2026-11-05 was within the original graph envelope but was **self-intersecting**. The AOI was not accepted or used for clipping. Shapely's validator rejects this geometry, and the updated editor now blocks crossed edges and unsafe polygon closure before exporting. The original file should be retained only as an unapproved draft, not automatically repaired with `buffer(0)` or a convex hull because these methods silently change the research boundary. Draw a fresh perimeter that follows the actual intended boundary, and retain the new GeoJSON for review.
