"""Offline regional-PBF → local OSM XML → SUMO for the Parnaíba study.

The immutable Geofabrik source is downloaded explicitly by the researcher.
This module NEVER calls Overpass, never modifies the reference GraphML, and
keeps regional extraction separate from the earlier tiled-Overpass workflow.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

from .sumo_bridge import (
    SOURCE, EXPECTED_SHA256, compute_bbox, digest,
    check_sumo, inspect_sumo_network, resolve_sumo_home,
    run_checked, validate_osm_xml, write_json,
)
import osmnx as ox

SNAPSHOT = "nordeste-261103"
SOURCE_URL = (
    "https://download.geofabrik.de/south-america/brazil/"
    + SNAPSHOT + ".osm.pbf"
)
DEFAULT_PBF = Path("data/raw/osm") / (SNAPSHOT + ".osm.pbf")
DEFAULT_MD5 = DEFAULT_PBF.with_name(DEFAULT_PBF.name + ".md5")
DEFAULT_OSM = Path("data/raw/osm/parnaiba_geofabrik_20261103.osm.xml")
DEFAULT_NET = Path("data/sumo/parnaiba_geofabrik_20261103.net.xml")
PLAN = Path("reports/parnaiba_regional_plan.json")
REPORT = Path("reports/parnaiba_regional_import.json")


def file_hashes(path: Path) -> dict:
    hashes = {"md5": hashlib.md5(), "sha256": hashlib.sha256()}
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            for h in hashes.values():
                h.update(chunk)
    return {key: h.hexdigest() for key, h in hashes.items()}


def verify_pbf(path: Path, sidecar: Path) -> dict:
    """Check Geofabrik's independently provided MD5, also record SHA-256."""
    if not path.is_file() or not sidecar.is_file():
        raise ValueError(
            "Missing PBF or its .md5 checksum. Download the frozen dated "
            "Geofabrik files before extracting."
        )
    text = sidecar.read_text(encoding="utf-8-sig").strip()
    match = re.search(r"\b[0-9a-fA-F]{32}\b", text)
    if not match:
        raise ValueError("Geofabrik .md5 file contains no valid MD5 checksum.")
    expected = match.group(0).lower()
    hashes = file_hashes(path)
    if hashes["md5"].lower() != expected:
        raise ValueError("Regional PBF checksum differs from Geofabrik MD5; do not use.")
    return {
        "file": str(path),
        "checksum_file": str(sidecar),
        "size_bytes": path.stat().st_size,
        "expected_md5": expected,
        "verified_md5": hashes["md5"],
        "sha256": hashes["sha256"],
        "source_url": SOURCE_URL,
        "snapshot_name": SNAPSHOT,
        "integrity": "MATCHES_GEOFABRIK_MD5",
    }


def select_local_roads(osm_source: Path, bbox: tuple[float, ...], osm_output: Path) -> dict:
    """Four streaming passes, preserving complete node refs for selected roads.

    Select OSM highway ways with any vertex in the bbox. Restriction relations
    are copied only when ALL their referenced nodes/ways are included.
    This selects a *candidate* road subset; it is NOT a perfect polygon clip.
    """
    try:
        import osmium
    except ImportError as exc:
        raise RuntimeError(
            "Pyosmium is required. Install with "
            "python -m pip install --only-binary=:all: osmium==4.3.2"
        ) from exc

    if not osm_source.is_file():
        raise ValueError(f"Regional source missing: {osm_source}")
    if osm_output.exists():
        raise ValueError(f"Refusing to overwrite candidate OSM XML: {osm_output}")
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Invalid WGS84 bbox.")
    local_nodes: set[int] = set()

    class InsideNodes(osmium.SimpleHandler):
        def node(self, node):
            loc = node.location
            if loc.valid() and west <= loc.lon <= east and south <= loc.lat <= north:
                local_nodes.add(int(node.id))

    InsideNodes().apply_file(str(osm_source))
    if not local_nodes:
        raise ValueError("No OSM nodes found inside the city bounding box.")

    ways: set[int] = set()
    required_nodes: set[int] = set()

    class SelectRoads(osmium.SimpleHandler):
        def way(self, way):
            if "highway" not in way.tags:
                return
            refs = [int(ref.ref) for ref in way.nodes]
            if any(ref in local_nodes for ref in refs):
                ways.add(int(way.id))
                required_nodes.update(refs)

    SelectRoads().apply_file(str(osm_source))
    if not ways or not required_nodes:
        raise ValueError("No OSM road ways selected; review regional coverage.")

    restrictions: set[int] = set()
    dropped_restrictions = 0
    candidate_restrictions = 0

    class SelectRestrictions(osmium.SimpleHandler):
        def relation(self, rel):
            nonlocal dropped_restrictions, candidate_restrictions
            if rel.tags.get("type") != "restriction":
                return
            members = [(str(m.type), int(m.ref)) for m in rel.members]
            if not any(kind == "w" and ref in ways for kind, ref in members):
                return
            candidate_restrictions += 1
            # Never emit a restriction with unresolved member references.
            if members and all(
                (kind == "w" and ref in ways)
                or (kind == "n" and ref in required_nodes)
                for kind, ref in members
            ):
                restrictions.add(int(rel.id))
            else:
                dropped_restrictions += 1

    SelectRestrictions().apply_file(str(osm_source))

    counts = {"nodes": 0, "ways": 0, "restrictions": 0}

    osm_output.parent.mkdir(parents=True, exist_ok=True)
    # Temporary filename must still end with .osm.xml so libosmium selects XML.
    with tempfile.TemporaryDirectory(prefix="parnaiba_extract_", dir=osm_output.parent) as td:
        temp_path = Path(td) / "candidate.osm.xml"
        with osmium.SimpleWriter(str(temp_path)) as writer:
            class CopySubset(osmium.SimpleHandler):
                def node(self, node):
                    if int(node.id) in required_nodes:
                        writer.add_node(node)
                        counts["nodes"] += 1

                def way(self, way):
                    if int(way.id) in ways:
                        writer.add_way(way)
                        counts["ways"] += 1

                def relation(self, rel):
                    if int(rel.id) in restrictions:
                        writer.add_relation(rel)
                        counts["restrictions"] += 1

            CopySubset().apply_file(str(osm_source))
        if counts["nodes"] < len(required_nodes):
            raise ValueError(
                "Regional extract has missing highway node references. "
                "Refusing to create incomplete OSM XML."
            )
        if counts["ways"] != len(ways):
            raise ValueError("Regional extract has missing highway ways.")
        stats = validate_osm_xml(temp_path)
        os.replace(temp_path, osm_output)

    return {
        "file": str(osm_output),
        "bbox_west_south_east_north": list(bbox),
        "selected_local_node_ids": len(local_nodes),
        "selected_highway_ways": len(ways),
        "required_way_nodes": len(required_nodes),
        "complete_restrictions_written": counts["restrictions"],
        "restrictions_dropped_incomplete": dropped_restrictions,
        "candidate_restrictions": candidate_restrictions,
        "xml_counts": stats,
        "sha256": digest(osm_output),
        "warning": (
            "Candidate extraction selects highway ways with at least one "
            "node inside the bbox; roads that geometrically cross the bbox "
            "without inside vertices may be missed. Only reference-complete "
            "restriction relations are retained. Verify coverage and turns "
            "against the reference GraphML and field evidence."
        ),
    }


def base_plan(graph: Path, margin_deg: float) -> dict:
    if not graph.is_file():
        raise ValueError(f"Original GraphML missing: {graph}")
    source_hash = digest(graph)
    if source_hash != EXPECTED_SHA256:
        raise ValueError("Original GraphML hash differs from the known reference.")
    original = ox.load_graphml(filepath=graph)
    return {
        "status": "REGIONAL_PBF_PLANNED_NOT_DOWNLOADED",
        "graph_reference": str(graph),
        "graph_sha256": source_hash,
        "original_nodes": original.number_of_nodes(),
        "original_directed_edges": original.number_of_edges(),
        "bbox_west_south_east_north": list(compute_bbox(original, margin_deg)),
        "bbox_margin_deg": margin_deg,
        "source": "Geofabrik OSM regional PBF, dated file",
        "source_url": SOURCE_URL,
        "snapshot": SNAPSHOT,
        "expected_pbf": str(DEFAULT_PBF),
        "pbf_md5_sidecar": str(DEFAULT_MD5),
        "note": (
            "Bounding box is not the official municipal boundary. "
            "Network maps, OSM versions and source date differ from the "
            "earlier OSMnx extraction. Road/traffic conclusions not calibrated."
        ),
    }


def regional_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local dated Geofabrik PBF-to-SUMO import (no Overpass calls)."
    )
    parser.add_argument("command", choices=("plan", "verify", "extract", "convert", "inspect"))
    parser.add_argument("--reference", type=Path, default=SOURCE)
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF)
    parser.add_argument("--md5-file", type=Path, default=DEFAULT_MD5)
    parser.add_argument("--osm", type=Path, default=DEFAULT_OSM)
    parser.add_argument("--net", type=Path, default=DEFAULT_NET)
    parser.add_argument("--plan-file", type=Path, default=PLAN)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--margin-deg", type=float, default=0.002)
    parser.add_argument("--sumo-home", default=None)
    args = parser.parse_args(argv)

    try:
        if args.command == "inspect":
            if not args.net.is_file():
                raise ValueError(f"SUMO network missing: {args.net}")
            print(json.dumps(inspect_sumo_network(args.net), indent=2))
            return 0

        plan = base_plan(args.reference, args.margin_deg)
        if args.command == "plan":
            write_json(args.plan_file, plan)
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0

        verified = verify_pbf(args.pbf, args.md5_file)
        if args.command == "verify":
            print(json.dumps(verified, ensure_ascii=False, indent=2))
            return 0

        if args.command == "extract":
            if args.report.exists():
                raise ValueError("A regional extraction report exists; refusing to overwrite.")
            extracted = select_local_roads(
                args.pbf, tuple(plan["bbox_west_south_east_north"]), args.osm
            )
            report = {
                **plan,
                "status": "OSM_EXTRACTED_NOT_CONVERTED",
                "verified_regional_pbf": verified,
                "extracted_osm": extracted,
                "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            write_json(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if not args.report.is_file():
            raise ValueError("Extraction report missing: run extract first.")
        previous = json.loads(args.report.read_text(encoding="utf-8"))
        if previous.get("status") != "OSM_EXTRACTED_NOT_CONVERTED":
            raise ValueError("Report not in an extract-ready state; inspect before converting.")
        if previous.get("bbox_west_south_east_north") != plan["bbox_west_south_east_north"]:
            raise ValueError("Study-area bbox differs from extraction report.")
        if previous.get("graph_sha256") != plan["graph_sha256"]:
            raise ValueError("Reference graph hash differs from extraction report.")
        if previous.get("verified_regional_pbf", {}).get("sha256") != verified["sha256"]:
            raise ValueError("Regional snapshot hash differs from extraction report.")
        if not args.osm.is_file() or digest(args.osm) != previous.get("extracted_osm", {}).get("sha256"):
            raise ValueError("Extracted OSM XML changed or is missing; refusing conversion.")
        validate_osm_xml(args.osm)
        home = resolve_sumo_home(args.sumo_home)
        if home is None:
            raise ValueError("SUMO installation not detected; run SUMO doctor.")
        if args.net.exists():
            raise ValueError("SUMO network already exists; refusing overwrite.")
        args.net.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="regional_sumo_", dir=args.net.parent) as td:
            candidate = Path(td) / "candidate.net.xml"
            exe = home / "bin" / ("netconvert.exe" if os.name == "nt" else "netconvert")
            run_checked([
                str(exe), "--osm-files", str(args.osm.resolve()),
                "--output-file", str(candidate.resolve()),
                "--keep-edges.by-vclass", "passenger",
                "--osm.turn-lanes", "true",
            ], timeout=3600)
            if not candidate.is_file() or candidate.stat().st_size == 0:
                raise ValueError("netconvert did not create a valid output.")
            structure = inspect_sumo_network(candidate)
            if structure["non_internal_sumo_edges"] == 0:
                raise ValueError("No passenger-accessible SUMO edges produced.")
            os.replace(candidate, args.net)

        report = {
            **previous,
            "status": "SUMO_NETWORK_CREATED_UNCALIBRATED",
            "sumo_network": str(args.net),
            "sumo_network_sha256": digest(args.net),
            "sumo_structure": structure,
            "converted_at_utc": datetime.now(timezone.utc).isoformat(),
            "warning": (
                "This is a traffic-free computational road model, not "
                "measured travel speed or validated traffic volume."
            ),
        }
        write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    except (ValueError, RuntimeError, OSError, ET.ParseError) as exc:
        parser.error(str(exc))
    return 2


def main() -> int:
    return regional_main()


if __name__ == "__main__":
    raise SystemExit(main())
