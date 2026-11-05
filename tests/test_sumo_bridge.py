"""Offline unit tests: no SUMO, Overpass or Internet required."""
import json
import xml.etree.ElementTree as ET

import networkx as nx
import pytest

from urban_mobility_lab.sumo_bridge import (
    build_osmget_command, compute_bbox, expected_osm_files, inspect_sumo_network, resolve_sumo_home,
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

def test_auto_discover_versioned_msi_installation(tmp_path, monkeypatch):
    """MSI installs to Program Files/sumo-VERSION, not always Eclipse/Sumo."""
    import os
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "x86"))
    monkeypatch.delenv("SUMO_HOME", raising=False)
    home = tmp_path / "sumo-1.28.0"
    (home / "bin").mkdir(parents=True)
    (home / "tools").mkdir()
    exe = "netconvert.exe" if os.name == "nt" else "netconvert"
    (home / "bin" / exe).write_text("test only")
    (home / "tools" / "osmGet.py").write_text("test only")
    assert resolve_sumo_home() == home.resolve()
    assert resolve_sumo_home(str(home / "bin")) == home.resolve()

def test_doctor_does_not_require_executable_to_run(tmp_path):
    """Detection works even if probing a fake test executable fails."""
    from urban_mobility_lab.sumo_bridge import check_sumo
    import os
    home = tmp_path / "sumo-1.28.0"
    (home / "bin").mkdir(parents=True)
    (home / "tools").mkdir()
    exe = "netconvert.exe" if os.name == "nt" else "netconvert"
    (home / "bin" / exe).write_text("test only")
    (home / "tools" / "osmGet.py").write_text("test only")
    result = check_sumo(str(home))
    assert result["sumo_detected"] is True
    assert result["sumo_home"] == str(home.resolve())
    assert result["netconvert_version"] in ("unavailable", None)

def test_osmget_command_preserves_negative_longitude_as_argument(tmp_path):
    import argparse
    bbox = [-41.8464173, -3.1032097, -41.6627259, -2.8057393]
    argv = build_osmget_command(
        "python.exe", tmp_path / "osmGet.py", bbox,
        4, "parnaiba_full", tmp_path,
    )
    # This equals-sign syntax is required for negative comma-separated values.
    assert argv[2] == "--bbox=-41.8464173,-3.1032097,-41.6627259,-2.8057393"
    assert "--bbox" not in argv
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox")
    parser.add_argument("--tiles")
    parser.add_argument("--prefix")
    parser.add_argument("--output-dir")
    parser.add_argument("--retries")
    parser.add_argument("--retry-delay")
    options = parser.parse_args(argv[2:])
    assert options.bbox == "-41.8464173,-3.1032097,-41.6627259,-2.8057393"
    assert options.tiles == "4"


def test_osmget_command_rejects_bbox_out_of_order(tmp_path):
    with pytest.raises(ValueError, match="bbox"):
        build_osmget_command(
            "python", tmp_path / "osmGet.py",
            [-41.6, -3.1, -41.8, -2.8], 4, "parnaiba_full", tmp_path,
        )

