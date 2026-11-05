"""Document the complete stored municipal road graph as the initial study domain.

This module never crops or overwrites the original graph and never infers
vehicle flows from topology. Any optional candidate AOI is diagnostic ONLY.
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
from shapely.geometry import Point, Polygon, MultiPolygon
from pyproj import Geod

from .audit import audit_graph
from .roi import load_aoi_geojson

DEFAULT_GRAPH = Path("data/networks/parnaiba_drive.graphml")
DEFAULT_REPORT = Path("reports/parnaiba_full_scope.json")


def summarize_scope(
    graph: nx.MultiDiGraph,
    *,
    candidate: Polygon | MultiPolygon | None = None,
) -> dict[str, Any]:
    """Audit the unmodified network and optionally compare a smaller polygon."""
    structural = audit_graph(graph)
    report: dict[str, Any] = {
        "study_domain": "COMPLETE_STORED_DRIVABLE_NETWORK",
        "status": "CANDIDATE_FULL_MUNICIPAL_NETWORK_NOT_FIELD_VALIDATED",
        "network_was_cropped": False,
        "network_audit": structural,
        "interpretation": (
            "The full OSMnx GraphML is used unchanged as the domain. "
            "This is not proof of an official administrative boundary, "
            "complete mapping of all roads, observed traffic, or a running SUMO simulation."
        ),
    }
    if candidate is not None:
        if not candidate.is_valid or candidate.is_empty:
            raise ValueError("Candidate AOI must be a valid non-empty polygon.")
        inside = 0
        valid = 0
        for _, attrs in graph.nodes(data=True):
            try:
                lon, lat = float(attrs["x"]), float(attrs["y"])
            except (KeyError, TypeError, ValueError):
                continue
            valid += 1
            if candidate.covers(Point(lon, lat)):
                inside += 1
        geod = Geod(ellps="WGS84")
        geod_area_m2, _ = geod.geometry_area_perimeter(candidate)
        report["candidate_aoi_diagnostic_only"] = {
            "area_km2_geodesic": round(abs(geod_area_m2) / 1e6, 3),
            "aoi_bbox_wgs84": list(candidate.bounds),
            "nodes_inside_or_on_polygon": inside,
            "nodes_outside_polygon": valid - inside,
            "fraction_of_valid_graph_nodes_inside": (
                round(inside / valid, 6) if valid else None
            ),
            "warning": (
                "This candidate polygon does not clip the network and "
                "does not define the city boundary. Node proportions are "
                "not percentages of physical road length or municipality area."
            ),
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit citywide study scope without cutting the road graph."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--candidate-geojson",
        type=Path,
        default=None,
        help="Optional manual AOI for diagnostic comparison only; never clips.",
    )
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"Missing source GraphML: {args.input}")
    if args.candidate_geojson and not args.candidate_geojson.is_file():
        parser.error(f"Missing candidate GeoJSON: {args.candidate_geojson}")

    try:
        graph = ox.load_graphml(filepath=args.input)
        candidate = (
            load_aoi_geojson(args.candidate_geojson)
            if args.candidate_geojson else None
        )
        report = summarize_scope(graph, candidate=candidate)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    report["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["input_graph"] = str(args.input)
    report["input_graph_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    if args.candidate_geojson:
        report["candidate_geojson"] = str(args.candidate_geojson)
        report["candidate_geojson_sha256"] = hashlib.sha256(
            args.candidate_geojson.read_bytes()
        ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved full-domain report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
