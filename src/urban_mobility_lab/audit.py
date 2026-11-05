"""Reproducible structural audit of an OSMnx GraphML road network.

This audit checks road-network structure. It does not measure traffic, verify
real-world connectivity, or establish simulation validity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox


def audit_graph(graph: nx.MultiDiGraph) -> dict[str, Any]:
    """Return basic topology/geometry diagnostics without external requests."""
    if not graph.is_directed():
        raise ValueError("Expected a directed road graph.")
    if graph.number_of_nodes() == 0 or graph.number_of_edges() == 0:
        raise ValueError("Road graph cannot be empty.")

    weak_component_sizes = sorted(
        (len(component) for component in nx.weakly_connected_components(graph)),
        reverse=True,
    )
    strong_component_sizes = sorted(
        (len(component) for component in nx.strongly_connected_components(graph)),
        reverse=True,
    )

    valid_x: list[float] = []
    valid_y: list[float] = []
    for _, attributes in graph.nodes(data=True):
        try:
            x = float(attributes["x"])
            y = float(attributes["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            valid_x.append(x)
            valid_y.append(y)

    missing_or_invalid_lengths = 0
    nonpositive_lengths = 0
    total_directed_length_m = 0.0
    for _, _, attributes in graph.edges(data=True):
        try:
            length = float(attributes["length"])
        except (KeyError, TypeError, ValueError):
            missing_or_invalid_lengths += 1
            continue
        if not math.isfinite(length):
            missing_or_invalid_lengths += 1
        elif length <= 0:
            nonpositive_lengths += 1
        else:
            total_directed_length_m += length

    num_nodes = graph.number_of_nodes()
    return {
        "validation_status": "STRUCTURAL_AUDIT_ONLY_NOT_FIELD_VALIDATED",
        "nodes": num_nodes,
        "directed_edges": graph.number_of_edges(),
        "graph_crs": str(graph.graph.get("crs", "unknown")),
        "nodes_with_valid_xy": len(valid_x),
        "nodes_missing_valid_xy": num_nodes - len(valid_x),
        "bbox_in_graph_crs": (
            {
                "min_x": min(valid_x),
                "max_x": max(valid_x),
                "min_y": min(valid_y),
                "max_y": max(valid_y),
            }
            if valid_x
            else None
        ),
        "weakly_connected_components": len(weak_component_sizes),
        "largest_weak_component_nodes": weak_component_sizes[0],
        "largest_weak_component_node_share": round(
            weak_component_sizes[0] / num_nodes, 6
        ),
        "strongly_connected_components": len(strong_component_sizes),
        "largest_strong_component_nodes": strong_component_sizes[0],
        "largest_strong_component_node_share": round(
            strong_component_sizes[0] / num_nodes, 6
        ),
        "self_loop_edges": nx.number_of_selfloops(graph),
        "missing_or_invalid_edge_lengths": missing_or_invalid_lengths,
        "nonpositive_edge_lengths": nonpositive_lengths,
        "sum_positive_directed_edge_lengths_m": round(total_directed_length_m, 2),
        "interpretation": (
            "Values describe mapped topology only. Directed road lengths can "
            "double-count two-way physical roads; connected-component counts "
            "require map and field review. No vehicle flows or travel times "
            "were observed or calibrated."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a saved OSMnx road network.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/networks/parnaiba_drive.graphml"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/parnaiba_network_audit.json"),
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Also generate a PNG overview (requires optional viz dependencies).",
    )
    parser.add_argument(
        "--map-output",
        type=Path,
        default=Path("reports/parnaiba_network.png"),
    )
    args = parser.parse_args(argv)

    if not args.input.is_file():
        parser.error(f"GraphML file not found: {args.input}")

    graph = ox.load_graphml(filepath=args.input)
    report = audit_graph(graph)
    report["source_file"] = str(args.input)
    report["source_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    report["audited_at_utc"] = datetime.now(timezone.utc).isoformat()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Saved audit report: {args.output}")

    if args.plot:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as exc:
            parser.error("Plotting requires: python -m pip install -e '.[viz]'")
        if report["nodes_missing_valid_xy"]:
            parser.error("Cannot plot: some network nodes have no valid x/y.")
        args.map_output.parent.mkdir(parents=True, exist_ok=True)
        fig, _ = ox.plot_graph(
            graph,
            show=False,
            close=False,
            node_size=0,
            edge_linewidth=0.35,
            figsize=(11, 11),
        )
        fig.savefig(args.map_output, dpi=180, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved network overview: {args.map_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
