"use strict";
// DAVID: map controls, accessible status/ETA and responsive presentation.
// SHEK: fetchState() is the integration seam for a future real telemetry feed.
const $ = id => document.getElementById(id);
const map = L.map('campus-map', {tap:true}).setView([38.831,-77.307],16);
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}); // Optional: leave unchecked for a dependable offline demonstration.
L.control.scale({imperial:false}).addTo(map);
const colors = {walkways:'#15803d',buildings:'#2563eb',delivery:'#800030',restricted:'#dc2626'};
const groups = {};
const text = value => { const span=document.createElement('span');span.textContent=value;return span; };
for (const [key,color] of Object.entries(colors)) {
  groups[key] = L.geoJSON(null, {
    style:{color,weight:key==='walkways'?3:4,fillOpacity:.25},
    pointToLayer:(feature,ll)=>L.circleMarker(ll,{radius:7,color,fillOpacity:1}),
    onEachFeature:(feature,layer)=>{
      const p=feature.properties || {};
      const name = p.name && p.name!==key ? p.name : `Unnamed ${key==='walkways'?'walkway':key}`;
      const label = `${name}${p.osm_id?' · OSM '+p.osm_id:''}`;
      layer.bindPopup(text(label)).bindTooltip(text(label),{sticky:true});
    }
  }).addTo(map);
}
const outbound = L.polyline([],{color:'#7e22ce',weight:6}).addTo(map);
const returning = L.polyline([],{color:'#007c91',weight:3,dashArray:'7 9'}).addTo(map);
const closures = L.layerGroup().addTo(map);
const robot = L.circleMarker([38.831,-77.307],{radius:10,color:'#fff',weight:3,fillColor:'#111827',fillOpacity:1}).addTo(map);
robot.bindTooltip('SIM-01 · simulated robot');
let state=null, received=0, failed=false, busy=false, pollTimer, revision=-1;

// Retain the supplied matching field model and canvas renderer. Weighted
// nodes explain the field visually; visibility does not add any routing costs.
const heat=new WeightedHeatLayer().addTo(map);
const nodes=L.layerGroup(),sources=L.layerGroup();
L.control.layers({'Offline GIS background':L.layerGroup().addTo(map),'Online OpenStreetMap tiles':tiles},{
  'Walkways (team data)':groups.walkways,'Buildings (OSM outlines)':groups.buildings,
  'Delivery points (SIMULATED)':groups.delivery,'Access restrictions (team data)':groups.restricted,
  'Outbound route':outbound,'Return route':returning,'Demo closures':closures,'Weighted crowd heat (predicted)':heat,'Robot SIM-01':robot,'Routing-node crowd scores':nodes,'Weighted crowd sources':sources
},{collapsed:true}).addTo(map);
// Pan/zoom choices persist; polling never replaces the map or its layer control.
const latlngs = coords => coords.map(([x,y])=>[y,x]);
function fitRoute(){
  const points=state?.outbound.length?latlngs(state.outbound):[robot.getLatLng()];
  map.fitBounds(L.latLngBounds(points).pad(.2),{maxZoom:17});
}
function show(s){
  state=s;received=Date.now();failed=false;
  $('phase').textContent=(s.running?'Moving · ':'Paused · ')+s.phase;
  if(s.phase==='complete')$('phase').textContent='Complete · back at base';
  if(s.phase==='unavailable')$('phase').textContent='No valid route';
  $('eta-label').textContent=`ETA to ${s.eta_target} · ${s.rate}× demo clock`;
  const seconds=Math.ceil(s.eta_seconds || 0);
  $('eta').textContent=s.eta_seconds===null?'Unavailable':s.phase==='complete'?'Arrived':
    `${Math.floor(seconds/60)}m ${seconds%60}s${!s.running?' (paused)':''}`;
  $('distance').textContent=`${s.traveled_meters} / ${s.total_meters} m`;
  $('notice').classList.toggle('error',s.phase==='unavailable');
  $('notice').textContent=`SIMULATION · ${s.message} ${s.rate===10?'10× playback; ETA is accelerated demo time.':''}`;
  robot.setLatLng([s.coordinates[1],s.coordinates[0]]);
  if($('follow').checked) map.panTo(robot.getLatLng());
  if(s.revision!==revision) {
    revision=s.revision;
    outbound.setLatLngs(latlngs(s.outbound));returning.setLatLngs(latlngs(s.return_route));
    closures.clearLayers();nodes.clearLayers();sources.clearLayers();
    for(const b of s.blocked)L.polyline(latlngs(b.coordinates),{color:'#f00',weight:10}).bindPopup(text('SIMULATED blocked segment')).addTo(closures);
    for(const b of (s.forecast_return_blocked || []))L.polyline(latlngs(b.coordinates),{color:'#d97706',weight:9,dashArray:'4 5'}).bindPopup(text('SIMULATED forecast closure on return leg')).addTo(closures);
    for(const n of s.weighted_nodes)L.circleMarker([n.coordinates[1],n.coordinates[0]],{radius:4,color:`hsl(${120*(1-n.score)},90%,35%)`,fillOpacity:.8}).bindPopup(text(`Routing node ${n.node_id} · crowd score ${n.score} · NO separate node cost`)).addTo(nodes);
    for(const p of s.weighted_points)L.circleMarker([p.lat,p.lon],{radius:7,color:'#9a3412',fillOpacity:.7}).bindPopup(text(`${p.name} · intensity ${p.weight} × confidence ${p.confidence} · effective ${p.effective_weight.toFixed(3)} · source ${p.source} · updated ${p.updated_at} · ${p.half_life_minutes} min freshness half-life`)).addTo(sources);
    heat.setPoints(s.weighted_points);
    $('stop').value=s.stop.id;$('scenario').value=s.scenario;$('rate').value=String(s.rate);
  }
  // Heat stays at the scenario's planning snapshot so it agrees with route costs.
  $('start').disabled=!s.outbound.length || s.phase==='complete';
}
async function request(url,body){
  const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),5000);
  try{
    const response=await fetch(url,{cache:'no-store',signal:controller.signal,
      ...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
    const result=await response.json();if(!response.ok)throw new Error(result.error || response.status);return result;
  } finally {clearTimeout(timeout);}
}
function error(e){failed=true;$('notice').classList.add('error');$('notice').textContent='Connection failed — last displayed position may be stale. '+e.message;}
async function fetchState(){
  if(busy)return;busy=true;
  try{show(await request('/api/state'));}catch(e){error(e);}finally{busy=false;}
}
function schedule(){clearTimeout(pollTimer);pollTimer=setTimeout(async()=>{await fetchState();schedule();},Number($('poll').value));}
$('poll').onchange=async()=>{await fetchState();schedule();};
$('fit').onclick=fitRoute;
for(const action of ['start','pause','reset']) $(''+action).onclick=async()=>{
  try{show(await request('/api/action',{action}));schedule();}catch(e){error(e);}
};
$('apply').onclick=async()=>{
  $('apply').disabled=true;
  try{show(await request('/api/configure',{stop:$('stop').value,scenario:$('scenario').value,rate:Number($('rate').value)}));fitRoute();schedule();}
  catch(e){error(e);}finally{$('apply').disabled=false;}
};
setInterval(()=>{
  if(!received)return;
  const age=Math.floor((Date.now()-received)/1000),stale=failed||age>Math.max(15,Number($('poll').value)/1000*2.5);
  $('age').textContent=`${age}s ago${stale?' · STALE':''}`;
},500);
(async()=>{
  try{
    const [config,layers]=await Promise.all([request('/api/config'),request('/api/layers')]);
    const counts={walkways:0,buildings:0,delivery:0,restricted:0};
    for(const f of layers.features){const k=f.properties?.layer;if(groups[k]){groups[k].addData(f);counts[k]++;}}
    for(const stop of config.stops){
      const option=document.createElement('option');option.value=stop.id;option.textContent=stop.name;$('stop').appendChild(option);
      groups.delivery.addData({type:'Feature',properties:{name:stop.name+' · SIMULATED graph stop'},geometry:{type:'Point',coordinates:stop.coordinates}});counts.delivery++;
    }
    L.circleMarker([config.base[1],config.base[0]],{radius:8,color:'#172b3a',fillOpacity:1}).bindTooltip('Demo base · unverified pickup location').addTo(map);
    $('counts').textContent=Object.entries(counts).map(([k,v])=>`${k}: ${v}`).join(' | ');
    $('source').textContent=config.source+'. '+config.building_note;
    await fetchState();if(!state)throw new Error('No initial state');fitRoute();
    for(const id of ['stop','apply','pause','reset','fit'])$(id).disabled=false;
    schedule();
  }catch(e){error(e);}
})();
