"""Offline AOI tests using synthetic network geometry and polygons."""
import json
import networkx as nx
import pytest
from shapely.geometry import box
from urban_mobility_lab.roi import crop_network, load_aoi_geojson, make_editor

def write_aoi(tmp_path, geometries):
    path = tmp_path / "aoi.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": geom}
            for geom in geometries
        ],
    }), encoding="utf-8")
    return path

def test_load_one_polygon(tmp_path):
    geom = {"type": "Polygon", "coordinates": [[
        [-41.8, -3.0], [-41.7, -3.0], [-41.7, -2.9],
        [-41.8, -2.9], [-41.8, -3.0],
    ]]}
    polygon = load_aoi_geojson(write_aoi(tmp_path, [geom]))
    assert polygon.is_valid
    assert polygon.bounds == (-41.8, -3.0, -41.7, -2.9)

def test_reject_multiple_drawings(tmp_path):
    geom = {"type": "Polygon", "coordinates": [[
        [-41.8, -3.0], [-41.7, -3.0], [-41.7, -2.9], [-41.8, -3.0],
    ]]}
    with pytest.raises(ValueError, match="ONE"):
        load_aoi_geojson(write_aoi(tmp_path, [geom, geom]))

def test_reject_invalid_coordinates(tmp_path):
    geom = {"type": "Polygon", "coordinates": [[
        [200, -3.0], [210, -3.0], [210, -2.9], [200, -3.0],
    ]]}
    with pytest.raises(ValueError, match="WGS84"):
        load_aoi_geojson(write_aoi(tmp_path, [geom]))

def test_clip_keeps_source_untouched():
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:4326"
    for node, (x, y) in {
        1: (-41.80, -2.95),
        2: (-41.79, -2.95),
        3: (-41.60, -2.95),
        4: (-41.59, -2.95),
    }.items():
        graph.add_node(node, x=x, y=y)
    for u, v in [(1, 2), (2, 1), (2, 3), (3, 4)]:
        graph.add_edge(u, v, length=100)
    cropped = crop_network(
        graph,
        box(-41.81, -2.96, -41.78, -2.94),
        retain_border_edges=False,
    )
    assert set(cropped.nodes) == {1, 2}
    assert cropped.number_of_edges() == 2
    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 4

def test_reject_wrong_crs():
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:3857"
    graph.add_edge(1, 2)
    with pytest.raises(ValueError, match="EPSG:4326"):
        crop_network(graph, box(-41.81, -2.96, -41.78, -2.94))

def test_standalone_editor_writes_html_without_folium(tmp_path):
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:4326"
    graph.add_node(1, x=-41.8, y=-2.95)
    graph.add_node(2, x=-41.79, y=-2.94)
    graph.add_edge(1, 2, length=100)
    output = tmp_path / "map.html"
    make_editor(graph, output)
    html = output.read_text(encoding="utf-8")
    assert "Urban Mobility Lab" in html
    assert "const roads=" in html
    assert "parnaiba_urban_core.geojson" in html
    assert "leaflet" not in html.lower()
    assert "folium" not in html.lower()
    assert "new Blob" in html

