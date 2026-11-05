"""Offline unit tests; no external services or real-world data required."""

import networkx as nx
import pytest

from urban_mobility_lab.ingestion import summarize_network


def test_summarize_synthetic_graph() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-41.0, y=-2.9)
    graph.add_node(2, x=-41.1, y=-2.8)
    graph.add_edge(1, 2, length=120.5)
    graph.add_edge(2, 1, length=121.5)

    result = summarize_network(graph, place="Synthetic fixture", network_type="drive")

    assert result["nodes"] == 2
    assert result["directed_edges"] == 2
    assert result["sum_directed_edge_lengths_m"] == 242.0
    assert result["validation_status"] == "UNCALIBRATED_MAP_NETWORK"
    assert result["study_place_query"] == "Synthetic fixture"


def test_reject_empty_graph() -> None:
    with pytest.raises(ValueError, match="empty"):
        summarize_network(
            nx.MultiDiGraph(), place="Synthetic fixture", network_type="drive"
        )
