"""Download an OSM road graph and record basic provenance metadata.

This module imports *road geometry*, not observed traffic flow. The exported
graph must be visually and topologically verified before use in simulations.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox


DEFAULT_PLACE = "Parnaíba, Piauí, Brazil"
DEFAULT_OUTPUT = Path("data/networks/parnaiba_drive.graphml")


def summarize_network(
    graph: nx.MultiDiGraph,
    *,
    place: str,
    network_type: str,
) -> dict[str, Any]:
    """Summarize a graph without claiming it represents measured traffic."""
    nodes = graph.number_of_nodes()
    edges = graph.number_of_edges()
    if nodes == 0 or edges == 0:
        raise ValueError("The downloaded road network is empty.")

    length_m = sum(
        float(attributes.get("length") or 0.0)
        for _, _, attributes in graph.edges(data=True)
    )

    return {
        "study_place_query": place,
        "network_type": network_type,
        "source": "OpenStreetMap via OSMnx",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "nodes": nodes,
        "directed_edges": edges,
        "sum_directed_edge_lengths_m": round(length_m, 2),
        "units": {
            "sum_directed_edge_lengths_m": "m",
        },
        "interpretation": (
            "Network geometry/topology only. The sum of directed edge lengths "
            "can count two-way physical roads twice. No traffic was measured."
        ),
        "validation_status": "UNCALIBRATED_MAP_NETWORK",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a drivable OSM network for a research study area."
    )
    parser.add_argument("--place", default=DEFAULT_PLACE)
    parser.add_argument(
        "--network-type",
        choices=("drive", "drive_service", "walk", "bike", "all", "all_public"),
        default="drive",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    graph = ox.graph_from_place(
        args.place,
        network_type=args.network_type,
        simplify=True,
        retain_all=True,
    )

    summary = summarize_network(
        graph, place=args.place, network_type=args.network_type
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, filepath=args.output)

    metadata_path = args.output.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved GraphML: {args.output}")
    print(f"Saved metadata: {metadata_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
