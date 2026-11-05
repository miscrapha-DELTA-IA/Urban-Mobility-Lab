"""Design an urban AOI and crop an existing OSMnx GraphML network.

Inputs are cartographic data; no traffic measurements are inferred.
The original network is always preserved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import networkx as nx
import osmnx as ox
from pyproj import CRS, Geod
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.validation import explain_validity

from .audit import audit_graph

SOURCE = Path("data/networks/parnaiba_drive.graphml")
AOI_PATH = Path("research/aoi/parnaiba_urban_core.geojson")
HTML_PATH = Path("reports/parnaiba_aoi_editor.html")
CROPPED_PATH = Path("data/networks/parnaiba_urban_core.graphml")
REPORT_PATH = Path("reports/parnaiba_urban_core_audit.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_aoi_geojson(path: Path) -> Polygon | MultiPolygon:
    """Load exactly one WGS84 polygon, including Folium Draw exports."""
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("AOI must be a GeoJSON object.")
    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list) or len(features) != 1:
            raise ValueError("Draw exactly ONE polygon/rectangle and export again.")
        feature = features[0]
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("GeoJSON collection must contain a Feature.")
        geometry = feature.get("geometry")
    elif kind == "Feature":
        geometry = payload.get("geometry")
    else:
        geometry = payload
    if not isinstance(geometry, dict):
        raise ValueError("No polygon geometry found in AOI file.")
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("AOI must be Polygon/MultiPolygon, not a point or line.")
    polygon = shape(geometry)
    if polygon.is_empty:
        raise ValueError("AOI polygon is empty.")
    if not polygon.is_valid:
        raise ValueError("Invalid AOI polygon: " + explain_validity(polygon) + ". Redraw the perimeter without crossing edges.")
    if polygon.area <= 0:
        raise ValueError("AOI polygon has zero area.")
    min_x, min_y, max_x, max_y = polygon.bounds
    if not (-180 <= min_x < max_x <= 180 and -90 <= min_y < max_y <= 90):
        raise ValueError("AOI must use WGS84 longitude, latitude (EPSG:4326).")
    return polygon


def crop_network(
    graph: nx.MultiDiGraph,
    polygon: Polygon | MultiPolygon,
    *,
    retain_border_edges: bool = True,
    largest_component_only: bool = False,
) -> nx.MultiDiGraph:
    """Crop nodes by AOI; optional border retention leaves some outside."""
    if graph.number_of_nodes() == 0 or graph.number_of_edges() == 0:
        raise ValueError("Input road network is empty.")
    if CRS.from_user_input(graph.graph.get("crs", "EPSG:4326")).to_epsg() != 4326:
        raise ValueError("Expected graph CRS EPSG:4326.")
    try:
        result = ox.truncate.truncate_graph_polygon(
            graph, polygon, truncate_by_edge=retain_border_edges
        )
    except (ValueError, nx.NetworkXError) as exc:
        raise ValueError("AOI contains no usable network: inspect your polygon.") from exc
    if result.number_of_nodes() == 0 or result.number_of_edges() == 0:
        raise ValueError("AOI contains no usable road edges; expand your polygon.")
    if largest_component_only:
        result = ox.truncate.largest_component(result, strongly=False)
    return result


def make_editor(graph: nx.MultiDiGraph, output: Path) -> None:
    """Generate a dependency-free interactive AOI editor, usable offline.

    The native canvas shows OSM road geometry embedded from the saved GraphML.
    Does not request map tiles or load remote scripts. Folium, a local web
    server and internet access are not required. The OSM reference link opens
    only when explicitly clicked.
    """
    xs = []
    ys = []
    for _, attrs in graph.nodes(data=True):
        xs.append(float(attrs["x"]))
        ys.append(float(attrs["y"]))
    if not xs or not ys:
        raise ValueError("Source graph has no valid nodes.")
    if CRS.from_user_input(graph.graph.get("crs", "EPSG:4326")).to_epsg() != 4326:
        raise ValueError("Editor expects EPSG:4326 geographic coordinates.")

    roads = []
    seen = set()
    for u, v, data in graph.edges(data=True):
        # Opposite directed copies are displayed once; crop retains original directions.
        endpoint_pair = tuple(sorted((str(u), str(v))))
        geometry = data.get("geometry")
        if geometry is not None and getattr(geometry, "geom_type", None) == "LineString":
            coords = [[round(float(x), 6), round(float(y), 6)]
                      for x, y in geometry.coords]
        else:
            a, b = graph.nodes[u], graph.nodes[v]
            coords = [
                [round(float(a["x"]), 6), round(float(a["y"]), 6)],
                [round(float(b["x"]), 6), round(float(b["y"]), 6)],
            ]
        # A pair may carry parallel geometries: keep the geometrically distinct ones.
        frozen_coords = tuple(tuple(point) for point in coords)
        signature = (endpoint_pair, frozen_coords)
        reverse = (endpoint_pair, tuple(reversed(frozen_coords)))
        if signature in seen or reverse in seen:
            continue
        seen.add(signature)
        roads.append(coords)

    bounds = [min(xs), min(ys), max(xs), max(ys)]  # west, south, east, north
    html = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Urban Mobility Lab · Delimitação urbana</title>
<style>
  :root{color-scheme:light;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
  *{box-sizing:border-box}
  body{margin:0;color:#16243a;background:#eff3f8}
  header{padding:12px 18px;background:#142a45;color:white}
  header strong{display:block;font-size:17px}
  header small{color:#c0d5e8}
  #toolbar{padding:9px 14px;display:flex;flex-wrap:wrap;align-items:center;gap:8px;background:#fff;border-bottom:1px solid #ddd}
  button,a.action{border:1px solid #ccd5e0;background:#fff;border-radius:7px;padding:8px 11px;color:#183450;font-weight:600;cursor:pointer;text-decoration:none;font-size:13px}
  button:hover,a.action:hover{background:#edf3fa}
  button.primary{background:#275f9f;color:white;border-color:#275f9f}
  button:disabled{opacity:.5;cursor:not-allowed}
  #status{margin-left:auto;font-size:12px;color:#4b5b6f}
  #stage{height:calc(100vh - 168px);min-height:380px;position:relative}
  canvas{width:100%;height:100%;display:block;touch-action:none;cursor:grab;background:#e8eff7}
  canvas.drawing{cursor:crosshair}
  footer{padding:10px 16px;background:#fff;border-top:1px solid #d9e3ed;font-size:12px;color:#465971;line-height:1.5}
  #hint{position:absolute;top:12px;left:12px;max-width:340px;padding:10px;background:rgba(255,255,255,.93);border-radius:7px;box-shadow:0 2px 9px #0002;font-size:12px;pointer-events:none}
  @media(max-width:660px){#stage{height:calc(100vh - 240px)}#status{width:100%;margin-left:0}}
</style>
</head>
<body>
<header><strong>URBAN MOBILITY LAB · PARNAÍBA</strong><small>Editor científico de área de estudo · rede viária local, sem mapas externos</small></header>
<div id="toolbar">
<button id="draw" class="primary">Desenhar polígono</button>
<button id="finish">Concluir</button>
<button id="undo">Desfazer ponto</button>
<button id="clear">Limpar</button>
<button id="reset">Enquadrar cidade</button>
<button id="export" class="primary">Exportar GeoJSON</button>
<a id="osm" class="action" href="https://www.openstreetmap.org/" target="_blank" rel="noopener">Conferir no OSM</a>
<span id="status">Iniciando editor…</span>
</div>
<div id="stage">
<canvas id="map" aria-label="Mapa interativo das ruas de Parnaíba. Use os botões para definir um polígono."></canvas>
<div id="hint"><strong>Mapa vetorial offline:</strong> as linhas são as ruas do GraphML original. Arraste para mover e use a roda do mouse para ampliar. Para conferir nomes e pontos de referência, clique em <strong>Conferir no OSM</strong> (abre uma página externa apenas se você clicar).<br>Selecione <strong>Desenhar polígono</strong>, marque ao menos 3 pontos <strong>em ordem ao redor do perímetro, sem cruzar as linhas</strong>, incluindo o Mirante e vias de acesso. Depois: <strong>Concluir → Exportar GeoJSON</strong>.</div>
</div>
<footer><strong>Natureza dos dados:</strong> ruas OSM (© OpenStreetMap contributors, ODbL), sem fluxo de veículos observado. Polígono manual para revisão, não limite urbano oficial. Sem requisições de imagens, scripts ou fontes externas; o link de referência abre apenas por escolha do usuário.</footer>
<script>
"use strict";
const roads=__ROADS_JSON__;
const bounds=__BOUNDS_JSON__;
const canvas=document.getElementById("map");
const ctx=canvas.getContext("2d");
const stage=document.getElementById("stage");
const statusEl=document.getElementById("status");
let centerLon=(bounds[0]+bounds[2])/2,centerLat=(bounds[1]+bounds[3])/2;
let zoom=12,drawMode=false,finished=false,points=[];
let w=1,h=1,dragging=false,downX=0,downY=0,moved=false,scheduled=false;
const R=Math.PI/180;
function project(lon,lat,z){
  const n=256*Math.pow(2,z), phi=Math.max(-85,Math.min(85,lat))*R;
  return {x:(lon+180)/360*n,y:(1-Math.asinh(Math.tan(phi))/Math.PI)/2*n};
}
function unproject(x,y,z){
  const n=256*Math.pow(2,z);
  return {lon:x/n*360-180,lat:Math.atan(Math.sinh(Math.PI*(1-2*y/n)))/R};
}
function px(lon,lat){
  const p=project(lon,lat,zoom),c=project(centerLon,centerLat,zoom);
  return {x:p.x-c.x+w/2,y:p.y-c.y+h/2};
}
function geo(x,y){
  const c=project(centerLon,centerLat,zoom);
  return unproject(c.x+x-w/2,c.y+y-h/2,zoom);
}
function orientation(a,b,c){
  return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
}
function withinSegment(a,b,p){
  const eps=1e-12;
  return p[0]>=Math.min(a[0],b[0])-eps&&p[0]<=Math.max(a[0],b[0])+eps&&
         p[1]>=Math.min(a[1],b[1])-eps&&p[1]<=Math.max(a[1],b[1])+eps;
}
function segmentsCross(a,b,c,d){
  const eps=1e-12;
  const o1=orientation(a,b,c),o2=orientation(a,b,d);
  const o3=orientation(c,d,a),o4=orientation(c,d,b);
  if(((o1>eps&&o2 < -eps)||(o1 < -eps&&o2>eps))&&
     ((o3>eps&&o4 < -eps)||(o3 < -eps&&o4>eps)))return true;
  if(Math.abs(o1)<=eps&&withinSegment(a,b,c))return true;
  if(Math.abs(o2)<=eps&&withinSegment(a,b,d))return true;
  if(Math.abs(o3)<=eps&&withinSegment(c,d,a))return true;
  if(Math.abs(o4)<=eps&&withinSegment(c,d,b))return true;
  return false;
}
function canAppendPoint(p){
  const n=points.length,eps=1e-7;
  if(points.some(q=>Math.abs(q[0]-p[0])<eps&&Math.abs(q[1]-p[1])<eps))return false;
  if(n<2)return true;
  // Test the new edge against every existing non-adjacent edge.
  for(let i=0;i<n-2;i++){
    if(segmentsCross(points[i],points[i+1],points[n-1],p))return false;
  }
  return true;
}
function isSimpleClosure(){
  const n=points.length;
  if(n<3)return false;
  let signedArea=0;
  for(let i=0;i<n;i++){
    const a=points[i],b=points[(i+1)%n];
    signedArea+=a[0]*b[1]-b[0]*a[1];
  }
  if(Math.abs(signedArea)<1e-10)return false;
  // The closing edge may touch only the first and last existing edges.
  for(let i=1;i<n-2;i++){
    if(segmentsCross(points[n-1],points[0],points[i],points[i+1]))return false;
  }
  return true;
}
function updateStatus(text){
  statusEl.textContent=text;
  canvas.classList.toggle("drawing",drawMode);
  document.getElementById("export").disabled=!finished;
  document.getElementById("finish").disabled=!drawMode||points.length<3;
  document.getElementById("undo").disabled=!points.length;
}
function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(render)}}
function resize(){
  const r=stage.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,2);
  w=Math.max(1,r.width);h=Math.max(1,r.height);
  canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  schedule();
}
function render(){
  scheduled=false;
  ctx.clearRect(0,0,w,h);ctx.fillStyle="#eaf0f8";ctx.fillRect(0,0,w,h);
  ctx.strokeStyle="rgba(19,81,142,0.87)";
  ctx.lineWidth=zoom>=14?1.6:1.0;
  ctx.beginPath();
  for(const road of roads){
    if(road.length<2)continue;
    let p=px(road[0][0],road[0][1]);
    ctx.moveTo(p.x,p.y);
    for(let i=1;i<road.length;i++){
      p=px(road[i][0],road[i][1]);ctx.lineTo(p.x,p.y);
    }
  }
  ctx.stroke();
  if(points.length){
    ctx.beginPath();
    let p=px(points[0][0],points[0][1]);ctx.moveTo(p.x,p.y);
    for(let i=1;i<points.length;i++){
      p=px(points[i][0],points[i][1]);ctx.lineTo(p.x,p.y);
    }
    if(finished)ctx.closePath();
    ctx.fillStyle="rgba(16,145,116,.21)";
    if(finished)ctx.fill();
    ctx.strokeStyle="#008b68";ctx.lineWidth=3;ctx.stroke();
    for(const [lon,lat] of points){
      const q=px(lon,lat);ctx.beginPath();ctx.arc(q.x,q.y,4,0,2*Math.PI);
      ctx.fillStyle="white";ctx.fill();ctx.stroke();
    }
  }
  const link=document.getElementById("osm");
  link.href="https://www.openstreetmap.org/#map/"+zoom+"/"+centerLat.toFixed(5)+"/"+centerLon.toFixed(5);
}
function fit(){
  const a=project(bounds[0],bounds[3],0),b=project(bounds[2],bounds[1],0);
  const zz=Math.floor(Math.min(
    Math.log2(Math.max(1,w-60)/Math.max(1,b.x-a.x)),
    Math.log2(Math.max(1,h-60)/Math.max(1,b.y-a.y)),16));
  zoom=Math.max(9,Math.min(16,zz));
  centerLon=(bounds[0]+bounds[2])/2;centerLat=(bounds[1]+bounds[3])/2;
  schedule();
}
canvas.addEventListener("pointerdown",e=>{
  downX=e.clientX;downY=e.clientY;moved=false;
  if(!drawMode){dragging=true;canvas.setPointerCapture(e.pointerId)}
});
canvas.addEventListener("pointermove",e=>{
  if(!dragging)return;
  const dx=e.clientX-downX,dy=e.clientY-downY;
  if(Math.abs(dx)+Math.abs(dy)>2)moved=true;
  const c=project(centerLon,centerLat,zoom);
  const next=unproject(c.x-dx,c.y-dy,zoom);
  centerLon=next.lon;centerLat=next.lat;downX=e.clientX;downY=e.clientY;
  schedule();
});
canvas.addEventListener("pointerup",()=>{dragging=false});
canvas.addEventListener("click",e=>{
  if(!drawMode||finished)return;
  const r=canvas.getBoundingClientRect(),p=geo(e.clientX-r.left,e.clientY-r.top);
  const candidate=[Number(p.lon.toFixed(7)),Number(p.lat.toFixed(7))];
  if(!canAppendPoint(candidate)){
    updateStatus("Ponto recusado: cruzamento ou repetição. Siga o contorno em ordem.");
    schedule();
    return;
  }
  points.push(candidate);
  updateStatus(points.length+" ponto(s). Clique em Concluir após contornar a área.");
  schedule();
});
canvas.addEventListener("wheel",e=>{
  e.preventDefault();
  const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
  const before=geo(x,y);zoom=Math.max(9,Math.min(19,zoom+(e.deltaY<0?1:-1)));
  const target=project(before.lon,before.lat,zoom);
  const newCenter=unproject(target.x-x+w/2,target.y-y+h/2,zoom);
  centerLon=newCenter.lon;centerLat=newCenter.lat;schedule();
},{passive:false});
document.getElementById("draw").onclick=()=>{
  drawMode=true;finished=false;points=[];
  updateStatus("Desenho ativado: clique para marcar pontos.");schedule();
};
document.getElementById("finish").onclick=()=>{
  if(points.length<3)return;
  if(!isSimpleClosure()){
    updateStatus("Contorno inválido: o último lado cruza outra linha ou tem área nula. Desfaça pontos.");
    schedule();
    return;
  }
  finished=true;drawMode=false;
  updateStatus("Polígono validado ("+points.length+" vértices). Exporte GeoJSON.");schedule();
};
document.getElementById("undo").onclick=()=>{
  if(finished){finished=false;drawMode=true}
  points.pop();updateStatus(points.length+" ponto(s).");schedule();
};
document.getElementById("clear").onclick=()=>{
  points=[];drawMode=false;finished=false;updateStatus("Seleção limpa.");schedule();
};
document.getElementById("reset").onclick=fit;
document.getElementById("export").onclick=()=>{
  if(!finished||points.length<3||!isSimpleClosure()){
    updateStatus("Exportação bloqueada: geometria inválida.");
    return;
  }
  const ring=[...points,points[0]];
  const result={type:"FeatureCollection",features:[{type:"Feature",
    properties:{name:"parnaiba_urban_core",status:"candidate_manual_AOI"},
    geometry:{type:"Polygon",coordinates:[ring]}}]};
  const blob=new Blob([JSON.stringify(result,null,2)],{type:"application/geo+json"});
  const url=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=url;a.download="parnaiba_urban_core.geojson";
  document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
  updateStatus("GeoJSON exportado. Revisar e guardar em research/aoi.");
};
window.addEventListener("resize",resize);
resize();fit();updateStatus("Mapa pronto. Arraste/zoom; desenhe UMA área.");
</script></body></html>"""
    html = html.replace("__ROADS_JSON__", json.dumps(roads, separators=(",", ":")))
    html = html.replace("__BOUNDS_JSON__", json.dumps(bounds))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")



def create_crop_report(
    original: nx.MultiDiGraph,
    cropped: nx.MultiDiGraph,
    polygon: Polygon | MultiPolygon,
    *,
    source_path: Path,
    polygon_path: Path,
    retain_border_edges: bool,
    largest_component_only: bool,
) -> dict[str, Any]:
    geod = Geod(ellps="WGS84")
    area_sqm, _ = geod.geometry_area_perimeter(polygon)
    return {
        "status": "CANDIDATE_URBAN_ROAD_GRAPH_NOT_FIELD_VALIDATED",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_graph": str(source_path),
        "source_graph_sha256": sha256(source_path),
        "aoi_polygon": str(polygon_path),
        "aoi_polygon_sha256": sha256(polygon_path),
        "aoi_bbox_wgs84": list(polygon.bounds),
        "aoi_area_km2_approx_geodesic": round(abs(area_sqm) / 1e6, 3),
        "retain_border_edges": retain_border_edges,
        "largest_component_only": largest_component_only,
        "original_nodes": original.number_of_nodes(),
        "original_directed_edges": original.number_of_edges(),
        "cropped_audit": audit_graph(cropped),
        "notes": (
            "Manual AOI not approved yet. Border retention may include "
            "nodes outside the polygon. Edges are not geometrically cut. "
            "Results describe topology, not measured vehicle traffic."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or apply a research AOI.")
    sub = parser.add_subparsers(dest="command", required=True)
    editor = sub.add_parser("editor", help="Generate interactive polygon editor.")
    editor.add_argument("--input", type=Path, default=SOURCE)
    editor.add_argument("--output", type=Path, default=HTML_PATH)
    clip = sub.add_parser("clip", help="Crop graph by exported AOI.")
    clip.add_argument("--input", type=Path, default=SOURCE)
    clip.add_argument("--polygon", type=Path, default=AOI_PATH)
    clip.add_argument("--output", type=Path, default=CROPPED_PATH)
    clip.add_argument("--report", type=Path, default=REPORT_PATH)
    clip.add_argument(
        "--strict-boundary",
        action="store_true",
        help="Drop nodes outside AOI even when an edge crosses the border.",
    )
    clip.add_argument(
        "--largest-component-only",
        action="store_true",
        help="Keep only the largest weakly connected component.",
    )
    args = parser.parse_args(argv)
    if not args.input.is_file():
        parser.error(f"Source GraphML missing: {args.input}")
    try:
        graph = ox.load_graphml(filepath=args.input)
        if args.command == "editor":
            make_editor(graph, args.output)
            print(f"AOI editor saved: {args.output}")
            print(f"Draw ONE polygon, export GeoJSON, then save at: {AOI_PATH}")
            return 0
        if not args.polygon.is_file():
            parser.error(f"AOI polygon missing: {args.polygon}")
        if args.output.resolve() == args.input.resolve():
            parser.error("Output must differ from source (no overwriting).")
        polygon = load_aoi_geojson(args.polygon)
        cropped = crop_network(
            graph,
            polygon,
            retain_border_edges=not args.strict_boundary,
            largest_component_only=args.largest_component_only,
        )
        report = create_crop_report(
            graph,
            cropped,
            polygon,
            source_path=args.input,
            polygon_path=args.polygon,
            retain_border_edges=not args.strict_boundary,
            largest_component_only=args.largest_component_only,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        ox.save_graphml(cropped, filepath=args.output)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Saved cropped GraphML: {args.output}")
        print(f"Saved audit: {args.report}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
