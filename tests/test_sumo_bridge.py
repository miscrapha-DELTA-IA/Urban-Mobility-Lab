"""Offline unit tests: no SUMO, Overpass or Internet required."""
import json
import xml.etree.ElementTree as ET

import networkx as nx
import pytest

from urban_mobility_lab.sumo_bridge import (
    compute_bbox, expected_osm_files, inspect_sumo_network, resolve_sumo_home,
)


def synthetic_graph():
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "epsg:4326"
    graph.add_node(1, x=-41.8, y=-3.1)
    graph.add_node(2, x=-41.7, y=-2.9)
    graph.add_edge(1, 2, length=100)
    return graph


def test_bbox_is_west_south_east_north():
    assert compute_bbox(synthetic_graph(), 0.002) == (
        -41.802, -3.102, -41.698, -2.898
    )


def test_bbox_rejects_bad_margin():
    with pytest.raises(ValueError, match="margin"):
        compute_bbox(synthetic_graph(), -0.01)


def test_bbox_requires_geo_coordinates():
    g = synthetic_graph()
    g.graph["crs"] = "epsg:3857"
    with pytest.raises(ValueError, match="4326"):
        compute_bbox(g)


def test_osm_get_tile_filename_contract(tmp_path):
    assert [p.name for p in expected_osm_files(tmp_path, "parnaiba_full", 4)] == [
        "parnaiba_full0_4.osm.xml",
        "parnaiba_full1_4.osm.xml",
        "parnaiba_full2_4.osm.xml",
        "parnaiba_full3_4.osm.xml",
    ]
    assert [p.name for p in expected_osm_files(tmp_path, "single", 1)] == [
        "single_bbox.osm.xml"
    ]


def test_osm_tiles_limits(tmp_path):
    with pytest.raises(ValueError, match="tiles"):
        expected_osm_files(tmp_path, "parnaiba", 0)
    with pytest.raises(ValueError, match="prefix"):
        expected_osm_files(tmp_path, "../../escape", 4)


def test_sumo_network_inspection_synthetic_xml(tmp_path):
    xml = """<net>
      <location origBoundary="-41.8,-3.1,-41.7,-2.9"/>
      <edge id="a"><lane id="a_0"/></edge>
      <edge id=":internal" function="internal"><lane id="int_0"/></edge>
      <junction id="j1" type="priority"/>
      <junction id=":i" type="internal"/>
      <tlLogic id="simulated" type="static"/>
    </net>"""
    path = tmp_path / "fixture.net.xml"
    path.write_text(xml, encoding="utf-8")
    result = inspect_sumo_network(path)
    assert result["non_internal_sumo_edges"] == 1
    assert result["non_internal_junctions"] == 1
    assert result["traffic_light_logic_elements"] == 1
    assert result["original_osm_bbox_reported_by_sumo"] == "-41.8,-3.1,-41.7,-2.9"


def test_doctor_resolves_synthetic_binary_layout(tmp_path):
    home = tmp_path / "SUMO"
    (home / "bin").mkdir(parents=True)
    (home / "tools").mkdir()
    # Unit test runs on Linux CI; executable naming follows the actual OS.
    import os
    executable = "netconvert.exe" if os.name == "nt" else "netconvert"
    (home / "bin" / executable).write_text("fake")
    (home / "tools" / "osmGet.py").write_text("fake")
    assert resolve_sumo_home(str(home)) == home.resolve()
