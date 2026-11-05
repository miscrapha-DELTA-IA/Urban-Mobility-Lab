"""Synthetic tests for reproducible regional PBF pipeline, no external downloads."""
from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
import pytest

from urban_mobility_lab.regional_pbf import (
    file_hashes, verify_pbf, select_local_roads, SNAPSHOT, SOURCE_URL,
)


def test_verifies_md5_and_sha256(tmp_path):
    content = b"synthetic regional data"
    pbf = tmp_path / "fake.osm.pbf"
    pbf.write_bytes(content)
    sidecar = tmp_path / "fake.osm.pbf.md5"
    sidecar.write_text(hashlib.md5(content).hexdigest() + "  fake.osm.pbf\n")
    verified = verify_pbf(pbf, sidecar)
    assert verified["integrity"] == "MATCHES_GEOFABRIK_MD5"
    assert verified["sha256"] == hashlib.sha256(content).hexdigest()
    assert verified["source_url"] == SOURCE_URL
    assert verified["snapshot_name"] == SNAPSHOT


def test_blocks_checksum_mismatch_and_missing_sidecar(tmp_path):
    pbf = tmp_path / "a.osm.pbf"
    pbf.write_bytes(b"data")
    sidecar = tmp_path / "a.osm.pbf.md5"
    with pytest.raises(ValueError, match="Missing"):
        verify_pbf(pbf, sidecar)
    sidecar.write_text("0" * 32 + "  a.osm.pbf\n")
    with pytest.raises(ValueError, match="differs"):
        verify_pbf(pbf, sidecar)


def test_extracts_complete_highway_ways_and_only_complete_restrictions(tmp_path):
    pytest.importorskip("osmium")
    source = tmp_path / "source.osm.xml"
    source.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="synthetic-fixture">
  <node id="1" lat="-3.0000" lon="-41.8000" version="1"/>
  <node id="2" lat="-3.0010" lon="-41.8010" version="1"/>
  <node id="3" lat="-3.0300" lon="-41.8300" version="1"/>
  <node id="4" lat="-3.1000" lon="-41.9000" version="1"/>
  <node id="5" lat="-3.1200" lon="-41.9000" version="1"/>
  <way id="10" version="1">
    <nd ref="1"/><nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="primary"/>
  </way>
  <way id="11" version="1">
    <nd ref="1"/><nd ref="3"/>
    <tag k="building" v="yes"/>
  </way>
  <way id="12" version="1">
    <nd ref="4"/><nd ref="5"/>
    <tag k="highway" v="residential"/>
  </way>
  <way id="13" version="1">
    <nd ref="2"/><nd ref="3"/>
    <tag k="highway" v="residential"/>
  </way>
  <relation id="40" version="1">
    <member type="way" ref="10" role="from"/>
    <member type="node" ref="2" role="via"/>
    <member type="way" ref="13" role="to"/>
    <tag k="type" v="restriction"/>
    <tag k="restriction" v="no_left_turn"/>
  </relation>
  <relation id="41" version="1">
    <member type="way" ref="10" role="from"/>
    <member type="node" ref="2" role="via"/>
    <member type="way" ref="12" role="to"/>
    <tag k="type" v="restriction"/>
    <tag k="restriction" v="no_right_turn"/>
  </relation>
</osm>""", encoding="utf-8")
    output = tmp_path / "local.osm.xml"
    result = select_local_roads(
        source, (-41.82, -3.02, -41.79, -2.99), output
    )
    assert result["selected_highway_ways"] == 2
    assert result["complete_restrictions_written"] == 1
    assert result["restrictions_dropped_incomplete"] == 1
    assert result["required_way_nodes"] == 3
    assert output.is_file()
    assert result["sha256"] == file_hashes(output)["sha256"]
    tree = ET.parse(output)
    assert {int(n.get("id")) for n in tree.findall("node")} == {1, 2, 3}
    assert {int(w.get("id")) for w in tree.findall("way")} == {10, 13}
    assert {int(r.get("id")) for r in tree.findall("relation")} == {40}
    with pytest.raises(ValueError, match="overwrite"):
        select_local_roads(
            source, (-41.82, -3.02, -41.79, -2.99), output
        )


def test_rejects_empty_or_invalid_bbox_without_output(tmp_path):
    pytest.importorskip("osmium")
    source = tmp_path / "empty.osm.xml"
    source.write_text('<osm version="0.6"></osm>', encoding="utf-8")
    out = tmp_path / "out.osm.xml"
    with pytest.raises(ValueError, match="bbox"):
        select_local_roads(source, (-41.7, -3.0, -41.8, -2.9), out)
    assert not out.exists()
    with pytest.raises(ValueError, match="No OSM nodes"):
        select_local_roads(source, (-41.8, -3.0, -41.7, -2.9), out)
    assert not out.exists()
