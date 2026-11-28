// WebGIS GIS AI - run with: python -m http.server 5500
const PATHS = {
  ortho: "../data/raster/orthophoto_normalized.tif",
  classification: "../data/raster/classification_veg_soil.tif",
  yolo: "../data/spatial_output/detections.geojson"
};
const BOUNDS = L.latLngBounds(
  [41.22306962931404, -81.70803475371355],
  [41.22930139232507, -81.70131519354833]
);
const $ = id => document.getElementById(id);
const map = L.map("map", {preferCanvas:true});
map.fitBounds(BOUNDS, {padding:[20,20]});

// CARTO basemap is used instead of the OSM tile endpoint that returned 403.
const base = L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  subdomains:"abcd", maxZoom:20,
  attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
}).addTo(map);

let orthoLayer, classLayer, yoloLayer, selectedLayer;
let features = [];

function esc(v) {
  return String(v ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function props(f) { return f.properties || {}; }
function conf(p) {
  const n = Number(p.confidence ?? p.conf ?? p.score);
  return Number.isFinite(n) ? n : null;
}
function pct(n) { return n === null ? "N/A" : (n*100).toFixed(1)+"%"; }
function label(f,i) {
  const p=props(f); return p.label ?? p.class_name ?? p.name ?? p.class ?? `Đối tượng ${p.id ?? i+1}`;
}
function idOf(f,i) { const p=props(f); return p.id ?? p.object_id ?? i+1; }
function style(f, active=false) {
  return {color:active?"#075985":"#e05b32",weight:active?4:2,
    fillColor:active?"#38bdf8":"#fb923c",fillOpacity:active?.38:.16};
}
function showDetails(f,i) {
  const p=props(f), c=conf(p);
  $("detail-title").textContent=`${label(f,i)} · #${idOf(f,i)}`;
  const rows=[["Nhãn",label(f,i)],["ID",idOf(f,i)],["Confidence",pct(c)],
    ["Kinh độ",p.longitude ?? p.lon],["Vĩ độ",p.latitude ?? p.lat],
    ["Pixel X",p.pixel_x],["Pixel Y",p.pixel_y]];
  $("detail-content").innerHTML=rows.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("");
  $("details").showModal();
}
function select(f,layer,i) {
  if(selectedLayer) selectedLayer.setStyle(style(selectedLayer.feature));
  selectedLayer=layer; layer.setStyle(style(f,true));
  document.querySelectorAll(".object").forEach(el=>el.classList.toggle("active",el.dataset.id===String(idOf(f,i))));
  if(layer.getBounds) map.fitBounds(layer.getBounds(),{maxZoom:19,padding:[25,25]});
  showDetails(f,i);
}
async function loadYolo() {
  const r=await fetch(PATHS.yolo);
  if(!r.ok) throw new Error(`GeoJSON HTTP ${r.status}`);
  const data=await r.json();
  features=Array.isArray(data.features)?data.features:[];
  yoloLayer=L.geoJSON(data,{
    style:f=>style(f),
    pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:7,color:"#c2410c",weight:2,fillColor:"#fb923c",fillOpacity:.85}),
    onEachFeature:(f,layer)=>{
      const i=features.indexOf(f), p=props(f);
      layer.bindPopup(`<b>${esc(label(f,i))}</b><br>ID: ${esc(idOf(f,i))}<br>Confidence: ${pct(conf(p))}`);
      layer.on("click",()=>select(f,layer,i));
    }
  }).addTo(map);
  $("count").textContent=features.length;
  const cs=features.map(f=>conf(props(f))).filter(v=>v!==null);
  $("confidence").textContent=pct(cs.length?cs.reduce((a,b)=>a+b,0)/cs.length:null);
  $("objects").replaceChildren();
  if(!features.length) $("objects").textContent="GeoJSON không có đối tượng.";
  features.forEach((f,i)=>{
    const p=props(f), b=document.createElement("button");
    b.className="object"; b.dataset.id=idOf(f,i);
    const coord=(p.latitude!=null&&p.longitude!=null)?`${Number(p.latitude).toFixed(5)}, ${Number(p.longitude).toFixed(5)}`:"Chọn để xem vị trí";
    b.innerHTML=`<span class="num">${i+1}</span><span><b>${esc(label(f,i))}</b><small>${esc(coord)}</small></span><em>${pct(conf(p))}</em>`;
    b.onclick=()=>{const layer=yoloLayer.getLayers().find(x=>x.feature===f);if(layer)select(f,layer,i);};
    $("objects").appendChild(b);
  });
}
async function loadOrtho() {
  if(typeof parseGeoraster!=="function"||typeof GeoRasterLayer!=="function") throw new Error("Không tải được thư viện GeoTIFF từ CDN.");
  const raster=await parseGeoraster(PATHS.ortho);
  orthoLayer=new GeoRasterLayer({georaster:raster,opacity:1,resolution:256,
    pixelValuesToColorFn:v=>{
      if(!v||v.length<3) return null;
      const [r,g,b,a]=v;
      if(r==null||g==null||b==null) return null;
      // Band 4 is treated as alpha when present.
      const alpha=v.length>=4&&a!=null?Math.max(0,Math.min(1,a/255)):1;
      return alpha<.01?null:`rgba(${r},${g},${b},${alpha})`;
    }});
  orthoLayer.addTo(map);
}
async function loadClass() {
  const raster=await parseGeoraster(PATHS.classification);
  classLayer=new GeoRasterLayer({georaster:raster,opacity:Number($("opacity").value)/100,resolution:256,
    pixelValuesToColorFn:v=>{
      const n=v?.[0];
      if(n==null||n===0) return null; // NoData
      if(Math.round(n)===1) return "rgba(34,197,94,0.82)";
      if(Math.round(n)===2) return "rgba(202,151,67,0.82)";
      return null;
    }});
}
function bindControls() {
  $("toggle-base").onchange=e=>e.target.checked?base.addTo(map):map.removeLayer(base);
  $("toggle-ortho").onchange=e=>{if(orthoLayer)(e.target.checked?orthoLayer.addTo(map):map.removeLayer(orthoLayer));};
  $("toggle-class").onchange=e=>{if(classLayer)(e.target.checked?classLayer.addTo(map):map.removeLayer(classLayer));};
  $("toggle-yolo").onchange=e=>{if(yoloLayer)(e.target.checked?yoloLayer.addTo(map):map.removeLayer(yoloLayer));};
  $("opacity").oninput=e=>{
    $("opacity-value").textContent=e.target.value+"%";
    if(classLayer) classLayer.setOpacity(Number(e.target.value)/100);
  };
  $("fit-area").onclick=()=>map.fitBounds(BOUNDS,{padding:[20,20]});
  $("fit-yolo").onclick=()=>{if(yoloLayer&&yoloLayer.getLayers().length)map.fitBounds(yoloLayer.getBounds(),{maxZoom:18,padding:[25,25]});};
  $("clear").onclick=()=>{
    if(selectedLayer)selectedLayer.setStyle(style(selectedLayer.feature));
    selectedLayer=null;
    document.querySelectorAll(".object").forEach(el=>el.classList.remove("active"));
  };
}
async function init() {
  bindControls();
  const results=await Promise.allSettled([loadOrtho(),loadClass(),loadYolo()]);
  const ok=results.map(r=>r.status==="fulfilled");
  if(!ok[0]) {console.error("Orthophoto:",results[0].reason);$("toggle-ortho").checked=false;}
  if(!ok[1]) {console.error("Classification:",results[1].reason);$("toggle-class").checked=false;}
  if(!ok[2]) {console.error("YOLO:",results[2].reason);$("objects").textContent="Lỗi tải GeoJSON: "+results[2].reason;}
  if(ok[0]&&$("toggle-ortho").checked)orthoLayer.addTo(map);
  if(ok[1]&&$("toggle-class").checked)classLayer.addTo(map);
  if(ok[2]&&$("toggle-yolo").checked)yoloLayer.addTo(map);
  const failed=ok.some(v=>!v);
  $("status").textContent=failed?"● Một số dữ liệu chưa tải được":"● Dữ liệu đã tải thành công";
  $("status").className=failed?"warning":"success";
  $("map-message").textContent=[
    ok[0]?"Orthophoto: OK":"Orthophoto: lỗi",
    ok[1]?"Classification: OK":"Classification: lỗi",
    ok[2]?"YOLO: OK":"YOLO: lỗi"
  ].join(" · ");
  map.fitBounds(BOUNDS,{padding:[20,20]});
}
init();
