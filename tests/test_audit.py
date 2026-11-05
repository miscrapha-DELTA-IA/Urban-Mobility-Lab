"""Synthetic offline tests of network structural diagnostics."""

import networkx as nx
import pytest

from urban_mobility_lab.audit import audit_graph


def test_audit_rejects_empty_graph() -> None:
    with pytest.raises(ValueError, match="empty"):
        audit_graph(nx.MultiDiGraph())


def test_audit_detects_components_and_invalid_lengths() -> None:
    graph = nx.MultiDiGraph()
    graph.add_node(1, x=-41.5, y=-2.9)
    graph.add_node(2, x=-41.4, y=-2.8)
    graph.add_node(3, x=-41.3, y=-2.7)
    graph.add_node(4)
    graph.add_edge(1, 2, length=100)
    graph.add_edge(2, 1, length=100)
    graph.add_edge(3, 4, length=-3)
    graph.add_edge(4, 3, length="missing")

    report = audit_graph(graph)
    assert report["nodes"] == 4
    assert report["directed_edges"] == 4
    assert report["weakly_connected_components"] == 2
    assert report["largest_weak_component_nodes"] == 2
    assert report["strongly_connected_components"] == 2
    assert report["nodes_missing_valid_xy"] == 1
    assert report["sum_positive_directed_edge_lengths_m"] == 200.0
    assert report["missing_or_invalid_edge_lengths"] == 1
    assert report["nonpositive_edge_lengths"] == 1
    assert report["validation_status"] == "STRUCTURAL_AUDIT_ONLY_NOT_FIELD_VALIDATED"
