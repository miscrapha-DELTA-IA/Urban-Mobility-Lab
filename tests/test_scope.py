"""Offline tests of candidate full-city domain selection."""
import networkx as nx
from shapely.geometry import box

from urban_mobility_lab.scope import summarize_scope


def graph_fixture():
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:4326"
    graph.add_node(1, x=-41.75, y=-2.92)
    graph.add_node(2, x=-41.74, y=-2.92)
    graph.add_node(3, x=-41.68, y=-2.85)
    graph.add_edge(1, 2, length=100.0)
    graph.add_edge(2, 3, length=200.0)
    return graph


def test_full_scope_never_crops_graph():
    graph = graph_fixture()
    before = (graph.number_of_nodes(), graph.number_of_edges())
    report = summarize_scope(graph)
    assert report["study_domain"] == "COMPLETE_STORED_DRIVABLE_NETWORK"
    assert report["network_was_cropped"] is False
    assert report["network_audit"]["nodes"] == 3
    assert report["network_audit"]["directed_edges"] == 2
    assert before == (graph.number_of_nodes(), graph.number_of_edges())


def test_candidate_aoi_only_compares_coverage():
    graph = graph_fixture()
    aoi = box(-41.77, -2.94, -41.73, -2.90)
    report = summarize_scope(graph, candidate=aoi)
    diag = report["candidate_aoi_diagnostic_only"]
    assert diag["nodes_inside_or_on_polygon"] == 2
    assert diag["nodes_outside_polygon"] == 1
    assert diag["area_km2_geodesic"] > 0
    assert report["network_audit"]["nodes"] == graph.number_of_nodes()
    assert report["network_was_cropped"] is False
