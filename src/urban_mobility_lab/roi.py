"""Design an urban AOI and crop an existing OSMnx GraphML network.

Inputs are cartographic data; no traffic measurements are inferred.
The original network is always preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
from pyproj import CRS, Geod
from shapely.geometry import MultiPolygon, Polygon, shape

from .audit import audit_graph

SOURCE = Path("data/networks/parnaiba_drive.graphml")
AOI_PATH = Path("research/aoi/parnaiba_urban_core.geojson")
HTML_PATH = Path("reports/parnaiba_aoi_editor.html")
CROPPED_PATH = Path("data/networks/parnaiba_urban_core.graphml")
REPORT_PATH = Path("reports/parnaiba_urban_core_audit.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_aoi_geojson(path: Path) -> Polygon | MultiPolygon:
    """Load exactly one WGS84 polygon, including Folium Draw exports."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("AOI must be a GeoJSON object.")
    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("Draw exactly ONE polygon/rectangle and export again.")
        feature = features[0]
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("GeoJSON collection must contain a Feature.")
        geometry = feature.get("geometry")
    elif kind == "Feature":
        geometry = payload.get("geometry")
    else:
        geometry = payload
    if not isinstance(geometry, dict):
        raise ValueError("No polygon geometry found in AOI file.")
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("AOI must be Polygon/MultiPolygon, not a point or line.")
    polygon = shape(geometry)
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
        raise ValueError("AOI polygon is empty or invalid.")
    min_x, min_y, max_x, max_y = polygon.bounds
    if not (-180 <= min_x < max_x <= 180 and -90 <= min_y < max_y <= 90):
        raise ValueError("AOI must use WGS84 longitude, latitude (EPSG:4326).")
    return polygon


def crop_network(
    graph: nx.MultiDiGraph,
    polygon: Polygon | MultiPolygon,
    *,
    retain_border_edges: bool = True,
    largest_component_only: bool = False,
) -> nx.MultiDiGraph:
    """Crop nodes by AOI; optional border retention leaves some outside."""
    if graph.number_of_nodes() == 0 or graph.number_of_edges() == 0:
        raise ValueError("Input road network is empty.")
    if CRS.from_user_input(graph.graph.get("crs", "EPSG:4326")).to_epsg() != 4326:
        raise ValueError("Expected graph CRS EPSG:4326.")
    try:
        result = ox.truncate.truncate_graph_polygon(
            graph, polygon, truncate_by_edge=retain_border_edges
        )
    except (ValueError, nx.NetworkXError) as exc:
        raise ValueError("AOI contains no usable network: inspect your polygon.") from exc
    if result.number_of_nodes() == 0 or result.number_of_edges() == 0:
        raise ValueError("AOI contains no usable road edges; expand your polygon.")
    if largest_component_only:
        result = ox.truncate.largest_component(result, strongly=False)
    return result


def make_editor(graph: nx.MultiDiGraph, output: Path) -> None:
    """Generate an HTML polygon editor. Map tiles are loaded by browser."""
    try:
        import folium
        from folium.plugins import Draw, Fullscreen
    except ImportError as exc:
        raise RuntimeError("Install UI dependencies: pip install -e '.[ui]'") from exc

    xs = [float(a["x"]) for _, a in graph.nodes(data=True)]
    ys = [float(a["y"]) for _, a in graph.nodes(data=True)]
    if not xs or not ys:
        raise ValueError("Source graph has no valid nodes.")
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    m = folium.Map(
        location=[(min_y + max_y) / 2, (min_x + max_x) / 2],
        tiles="OpenStreetMap",
        zoom_start=12,
        control_scale=True,
    )
    m.fit_bounds([[min_y, min_x], [max_y, max_x]])
    Draw(
        export=True,
        filename=AOI_PATH.name,
        position="topleft",
        show_geometry_on_click=False,
        draw_options={
            "polyline": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
            "polygon": {"allowIntersection": False},
            "rectangle": True,
        },
    ).add_to(m)
    Fullscreen().add_to(m)
    m.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;bottom:16px;left:16px;z-index:9999;'
            'background:#fff;padding:12px;max-width:340px;font:14px sans-serif;'
            'box-shadow:0 2px 8px #777">'
            '<strong>Urban Mobility Lab / AOI</strong><br>'
            'Zoom to Parnaíba urban core. Draw ONE polygon or rectangle '
            'using the left toolbar. Export GeoJSON in the upper right. '
            'Include Mirante and major approach roads. Review before SUMO. '
            'The basemap and drawing scripts require internet access.'
            '</div>'
        )
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output))


def create_crop_report(
    original: nx.MultiDiGraph,
    cropped: nx.MultiDiGraph,
    polygon: Polygon | MultiPolygon,
    *,
    source_path: Path,
    polygon_path: Path,
    retain_border_edges: bool,
    largest_component_only: bool,
) -> dict[str, Any]:
    geod = Geod(ellps="WGS84")
    area_sqm, _ = geod.geometry_area_perimeter(polygon)
    return {
        "status": "CANDIDATE_URBAN_ROAD_GRAPH_NOT_FIELD_VALIDATED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_graph": str(source_path),
        "source_graph_sha256": sha256(source_path),
        "aoi_polygon": str(polygon_path),
        "aoi_polygon_sha256": sha256(polygon_path),
        "aoi_bbox_wgs84": list(polygon.bounds),
        "aoi_area_km2_approx_geodesic": round(abs(area_sqm) / 1e6, 3),
        "retain_border_edges": retain_border_edges,
        "largest_component_only": largest_component_only,
        "original_nodes": original.number_of_nodes(),
        "original_directed_edges": original.number_of_edges(),
        "cropped_audit": audit_graph(cropped),
        "notes": (
            "Manual AOI not approved yet. Border retention may include "
            "nodes outside the polygon. Edges are not geometrically cut. "
            "Results describe topology, not measured vehicle traffic."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or apply a research AOI.")
    sub = parser.add_subparsers(dest="command", required=True)
    editor = sub.add_parser("editor", help="Generate interactive polygon editor.")
    editor.add_argument("--input", type=Path, default=SOURCE)
    editor.add_argument("--output", type=Path, default=HTML_PATH)
    clip = sub.add_parser("clip", help="Crop graph by exported AOI.")
    clip.add_argument("--input", type=Path, default=SOURCE)
    clip.add_argument("--polygon", type=Path, default=AOI_PATH)
    clip.add_argument("--output", type=Path, default=CROPPED_PATH)
    clip.add_argument("--report", type=Path, default=REPORT_PATH)
    clip.add_argument(
        "--strict-boundary",
        action="store_true",
        help="Drop nodes outside AOI even when an edge crosses the border.",
    )
    clip.add_argument(
        "--largest-component-only",
        action="store_true",
        help="Keep only the largest weakly connected component.",
    )
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"Source GraphML missing: {args.input}")
    try:
        graph = ox.load_graphml(filepath=args.input)
        if args.command == "editor":
            make_editor(graph, args.output)
            print(f"AOI editor saved: {args.output}")
            print(f"Draw ONE polygon, export GeoJSON, then save at: {AOI_PATH}")
            return 0
        if not args.polygon.is_file():
            parser.error(f"AOI polygon missing: {args.polygon}")
        if args.output.resolve() == args.input.resolve():
            parser.error("Output must differ from source (no overwriting).")
        polygon = load_aoi_geojson(args.polygon)
        cropped = crop_network(
            graph,
            polygon,
            retain_border_edges=not args.strict_boundary,
            largest_component_only=args.largest_component_only,
        )
        report = create_crop_report(
            graph,
            cropped,
            polygon,
            source_path=args.input,
            polygon_path=args.polygon,
            retain_border_edges=not args.strict_boundary,
            largest_component_only=args.largest_component_only,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(cropped, filepath=args.output)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Saved cropped GraphML: {args.output}")
        print(f"Saved audit: {args.report}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
