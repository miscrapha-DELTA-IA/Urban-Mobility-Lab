"""Import a frozen OSM road-network snapshot into Eclipse SUMO.

No calls to external map services in doctor, plan, or tests. Download requires
an explicit subcommand and acknowledgement. No vehicle flows are inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

import networkx as nx
import osmnx as ox

SOURCE = Path("data/networks/parnaiba_drive.graphml")
RAW = Path("data/raw/osm")
NET = Path("data/sumo/parnaiba_full.net.xml")
PREFIX = "parnaiba_full"
STUDY_REPORT = Path("reports/parnaiba_sumo_import.json")
EXPECTED_SHA256 = "05fb88f7a23f2f9865c9c2656f1a69937bf087776e94cc593728390db240b5d6"


def digest(path: Path) -> str:
    """Compute file SHA-256 in chunks to avoid large memory allocations."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def compute_bbox(graph: nx.MultiDiGraph, margin_deg: float = 0.002) -> tuple[float, ...]:
    """West,south,east,north of all graph nodes plus reproducible margin."""
    if not 0 <= margin_deg <= 0.05:
        raise ValueError("margin_deg must be between 0 and 0.05 degrees.")
    if str(graph.graph.get("crs", "")).lower() not in ("epsg:4326", "urn:ogc:def:crs:epsg::4326"):
        raise ValueError("Expected EPSG:4326 road graph.")
    if not graph.nodes:
        raise ValueError("Graph has no nodes.")
    xs = [float(attr["x"]) for _, attr in graph.nodes(data=True)]
    ys = [float(attr["y"]) for _, attr in graph.nodes(data=True)]
    if not (all(-180 <= x <= 180 for x in xs) and all(-90 <= y <= 90 for y in ys)):
        raise ValueError("Invalid WGS84 node coordinates.")
    return (
        round(min(xs) - margin_deg, 7),
        round(min(ys) - margin_deg, 7),
        round(max(xs) + margin_deg, 7),
        round(max(ys) + margin_deg, 7),
    )


def expected_osm_files(folder: Path, prefix: str, tiles: int) -> list[Path]:
    if not (1 <= tiles <= 16):
        raise ValueError("tiles must be an integer between 1 and 16.")
    if not prefix or not all(c.isalnum() or c in "-_" for c in prefix):
        raise ValueError("Invalid OSM filename prefix.")
    if tiles == 1:
        return [folder / (prefix + "_bbox.osm.xml")]
    return [folder / f"{prefix}{i}_{tiles}.osm.xml" for i in range(tiles)]


def _windows_sumo_environment() -> list[str]:
    """Read persisted SUMO_HOME after MSI installation in an older shell.

    The installer may update the Windows registry without refreshing a
    PowerShell session that was already open before installation.
    """
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    candidates = []
    for hive, key_path in (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "SUMO_HOME")
                if value:
                    candidates.append(os.path.expandvars(str(value)))
        except (FileNotFoundError, OSError):
            pass
    return candidates


def _sumo_candidate_homes(override: str | None = None) -> list[Path]:
    """Collect likely locations without crawling entire disk drives."""
    candidates: list[str] = []
    for entry in (override, os.environ.get("SUMO_HOME")):
        if entry:
            candidates.append(entry)
    candidates.extend(_windows_sumo_environment())

    for k, fallback in (
        ("ProgramFiles", r"C:\Program Files"),
        ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ):
        root = Path(os.environ.get(k, fallback))
        candidates.extend(str(root / folder) for folder in (
            "sumo-1.28.0", "sumo", "SUMO",
            "Eclipse/Sumo", "Eclipse/SUMO",
        ))
        # Match versioned MSI locations such as sumo-1.28.0 / sumo-1.29.0.
        if root.is_dir():
            candidates.extend(
                str(item) for item in root.glob("sumo-*") if item.is_dir()
            )
            eclipse = root / "Eclipse"
            if eclipse.is_dir():
                candidates.extend(
                    str(item) for item in eclipse.glob("*umo*") if item.is_dir()
                )

    local_programs = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs"
    if local_programs.is_dir():
        candidates.extend(
            str(item) for item in local_programs.glob("*umo*") if item.is_dir()
        )

    found = shutil.which("netconvert.exe") or shutil.which("netconvert")
    if found:
        candidates.append(str(Path(found).resolve().parent.parent))

    unique: list[Path] = []
    seen: set[str] = set()
    for item in candidates:
        home = Path(os.path.expandvars(item)).expanduser()
        if home.name.lower() == "bin":
            home = home.parent
        key = str(home).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(home)
    return unique


def resolve_sumo_home(override: str | None = None) -> Path | None:
    """Locate both SUMO executables and bundled scripts, without writes."""
    executable = "netconvert.exe" if os.name == "nt" else "netconvert"
    for home in _sumo_candidate_homes(override):
        if (
            (home / "bin" / executable).is_file()
            and (home / "tools" / "osmGet.py").is_file()
        ):
            return home.resolve()
    return None


def check_sumo(override: str | None = None) -> dict:
    home = resolve_sumo_home(override)
    executable = "netconvert.exe" if os.name == "nt" else "netconvert"
    netconvert = home / "bin" / executable if home else None
    version = None
    if netconvert:
        try:
            completed = subprocess.run(
                [str(netconvert), "--version"],
                capture_output=True, text=True, timeout=12,
                check=True,
            )
            lines = (completed.stdout or completed.stderr).strip().splitlines()
            version = lines[0] if lines else None
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            version = "unavailable"
    return {
        "sumo_detected": home is not None,
        "sumo_home": str(home) if home else None,
        "netconvert": str(netconvert) if netconvert else None,
        "netconvert_version": version,
        "osm_get_script": str(home / "tools" / "osmGet.py") if home else None,
        "suggestion": (
            "SUMO tools located."
            if home
            else "SUMO not found. Locate bin/netconvert.exe and tools/osmGet.py; pass --sumo-home followed by their parent directory."
        ),
    }


def inspect_sumo_network(path: Path) -> dict:
    """Read only XML structural elements; edge counts are not traffic values."""
    edges = 0
    junctions = 0
    tls = 0
    original_bounds = None
    for _, elem in ET.iterparse(str(path), events=("end",)):
        name = elem.tag
        if name == "edge" and elem.get("function") != "internal":
            edges += 1
        elif name == "junction" and elem.get("type") != "internal":
            junctions += 1
        elif name == "tlLogic":
            tls += 1
        elif name == "location":
            original_bounds = elem.get("origBoundary")
        elem.clear()
    return {
        "non_internal_sumo_edges": edges,
        "non_internal_junctions": junctions,
        "traffic_light_logic_elements": tls,
        "original_osm_bbox_reported_by_sumo": original_bounds,
        "warning": "SUMO segment/junction counts are not expected to equal simplified OSMnx graph counts. Traffic lights are not field-validated.",
    }


def run_checked(argv: list[str], timeout: int = 1800) -> None:
    print("Executing:", " ".join(argv), flush=True)
    try:
        subprocess.run(argv, check=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Process exceeded {timeout} seconds; inspect partial outputs before retrying.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"External command failed with exit code {exc.returncode}.") from exc


def make_plan(source: Path, tiles: int, margin_deg: float, prefix: str, raw: Path) -> dict:
    if not source.is_file():
        raise ValueError(f"Original GraphML not found: {source}")
    graph = ox.load_graphml(filepath=source)
    bbox = compute_bbox(graph, margin_deg)
    return {
        "status": "PREPARED_NOT_DOWNLOADED",
        "input_graph": str(source),
        "input_sha256": digest(source),
        "expected_original_sha256": EXPECTED_SHA256,
        "matches_reference_snapshot": digest(source) == EXPECTED_SHA256,
        "source_nodes": graph.number_of_nodes(),
        "source_directed_edges": graph.number_of_edges(),
        "bbox_west_south_east_north": list(bbox),
        "margin_degrees": margin_deg,
        "tiles": tiles,
        "osm_files": [str(p) for p in expected_osm_files(raw, prefix, tiles)],
        "note": "Bounding box includes areas outside the source graph boundary. Imported OSM network must be reconciled against reference graph. No traffic data.",
    }


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reproducible OSM-to-SUMO road import.")
    parser.add_argument("command", choices=["doctor", "plan", "download", "convert", "inspect"])
    parser.add_argument("--input", type=Path, default=SOURCE)
    parser.add_argument("--sumo-home", default=None)
    parser.add_argument("--tiles", type=int, default=4)
    parser.add_argument("--margin-deg", type=float, default=0.002)
    parser.add_argument("--prefix", default=PREFIX)
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--net", type=Path, default=NET)
    parser.add_argument("--report", type=Path, default=STUDY_REPORT)
    parser.add_argument("--confirm-download", action="store_true")
    parser.add_argument("--allow-new-reference", action="store_true",
                        help="Accept source graph with a different SHA-256 after manual review.")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            print(json.dumps(check_sumo(args.sumo_home), indent=2, ensure_ascii=False))
            return 0
        if args.command == "inspect":
            if not args.net.is_file():
                raise ValueError(f"SUMO network missing: {args.net}")
            print(json.dumps(inspect_sumo_network(args.net), indent=2))
            return 0

        plan = make_plan(args.input, args.tiles, args.margin_deg, args.prefix, args.raw_dir)
        if not plan["matches_reference_snapshot"] and not args.allow_new_reference:
            raise ValueError("GraphML SHA-256 differs from original checkpoint. Inspect source or use --allow-new-reference after review.")
        if args.command == "plan":
            write_json(args.report, plan)
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0

        home = resolve_sumo_home(args.sumo_home)
        if home is None:
            raise ValueError("SUMO installation not located. Run doctor first.")
        osm_files = expected_osm_files(args.raw_dir, args.prefix, args.tiles)
        if args.command == "download":
            if not args.confirm_download:
                raise ValueError("Explicitly pass --confirm-download to request data from Overpass.")
            if any(p.exists() for p in osm_files):
                raise ValueError("OSM output already exists. Inspect files rather than overwriting a reference snapshot.")
            args.raw_dir.mkdir(parents=True, exist_ok=True)
            get_script = home / "tools" / "osmGet.py"
            bbox_text = ",".join(str(n) for n in plan["bbox_west_south_east_north"])
            run_checked([
                sys.executable, str(get_script),
                "--bbox", bbox_text, "--tiles", str(args.tiles),
                "--prefix", args.prefix, "--output-dir", str(args.raw_dir.resolve()),
                "--retries", "2", "--retry-delay", "5",
            ], timeout=3600)
            if not all(p.is_file() and p.stat().st_size > 0 for p in osm_files):
                raise ValueError("One or more OSM tiles missing/empty. No successful snapshot recorded.")
            plan["status"] = "OSM_XML_DOWNLOADED_NOT_CONVERTED"
            plan["osm_file_sha256"] = {str(p): digest(p) for p in osm_files}
            plan["download_recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
            write_json(args.report, plan)
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 0

        if any(not p.is_file() or p.stat().st_size == 0 for p in osm_files):
            raise ValueError("OSM XML tiles missing/empty; run download first.")
        if args.net.exists():
            raise ValueError("SUMO network already exists; refusing to overwrite.")
        args.net.parent.mkdir(parents=True, exist_ok=True)
        netconvert = home / "bin" / ("netconvert.exe" if os.name == "nt" else "netconvert")
        run_checked([
            str(netconvert), "--osm-files",
            ",".join(str(p.resolve()) for p in osm_files),
            "--output-file", str(args.net.resolve()),
            "--keep-edges.by-vclass", "passenger",
            "--osm.turn-lanes", "true",
        ], timeout=3600)
        if not args.net.is_file() or args.net.stat().st_size == 0:
            raise RuntimeError("SUMO conversion completed without a valid output file.")
        plan["status"] = "SUMO_NETWORK_CREATED_UNCALIBRATED"
        plan["osm_file_sha256"] = {str(p): digest(p) for p in osm_files}
        plan["sumo_network"] = str(args.net)
        plan["sumo_network_sha256"] = digest(args.net)
        plan["sumo_structure"] = inspect_sumo_network(args.net)
        plan["converted_at_utc"] = datetime.now(timezone.utc).isoformat()
        plan["validation_caution"] = "No route demand, observed signal plans, field traffic validation or urban accuracy guarantees."
        write_json(args.report, plan)
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, RuntimeError, ET.ParseError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
