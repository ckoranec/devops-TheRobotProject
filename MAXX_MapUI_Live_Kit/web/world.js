"use strict";
// DAVID: map controls, accessible status/ETA and responsive presentation.
// SHEK: fetchState() is the integration seam for a future real telemetry feed.
const $ = id => document.getElementById(id);
const map = L.map('campus-map', {tap:true}).setView([38.831,-77.307],16);
const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
}).addTo(map); // Match the team's familiar OSM background; offline GIS is still available.
L.control.scale({imperial:false}).addTo(map);
const colors = {walkways:'#15803d',buildings:'#2563eb',delivery:'#800030',restricted:'#dc2626'};
const groups = {};
const text = value => { const span=document.createElement('span');span.textContent=value;return span; };
for (const [key,color] of Object.entries(colors)) {
  groups[key] = L.geoJSON(null, {
    style:{color,weight:key==='walkways'?4:key==='restricted'?4:3,fillOpacity:.25,...(key==='restricted'?{dashArray:'6 4'}:{})},
    pointToLayer:(feature,ll)=>L.circleMarker(ll,{radius:7,color,fillOpacity:1}),
    onEachFeature:(feature,layer)=>{
      const p=feature.properties || {};
      const name = p.name && p.name!==key ? p.name : `Unnamed ${key==='walkways'?'walkway':key}`;
      const rules=Object.entries(p.access_tags||{}).map(([k,v])=>k+'='+v).join(', ');
      const label = `${name}${p.osm_id?' · OSM '+p.osm_id:''}${rules?' · '+rules:''}`;
      layer.bindPopup(text(label)).bindTooltip(text(label),{sticky:true});
    }
  }).addTo(map);
}
const outbound = L.polyline([],{color:'#7e22ce',weight:7}).addTo(map);
const returning = L.polyline([],{color:'#f97316',weight:4,dashArray:'10 10',opacity:1}).addTo(map);
const closures = L.layerGroup().addTo(map);
const restrictionSymbols=L.layerGroup().addTo(map);
const projectAreas=L.geoJSON(null,{style:f=>({color:f.properties.Project_Phase==='Construction'?'#c2410c':'#64748b',weight:2,fillOpacity:.1}),onEachFeature:(f,l)=>l.bindPopup(text(f.properties.Project+' · '+f.properties.Project_Phase+' · published project area, not a confirmed walkway closure'))}); // Project areas are optional; keep the classic background unobscured.
const robot = L.circleMarker([38.831,-77.307],{radius:10,color:'#fff',weight:3,fillColor:'#111827',fillOpacity:1}).addTo(map);
robot.bindTooltip('SIM-01 · software robot');
let state=null, received=0, failed=false, busy=false, pollTimer, revision=-1;

// Retain the supplied matching field model and canvas renderer. Weighted
// nodes explain the field visually; visibility does not add any routing costs.
const heat=new WeightedHeatLayer().addTo(map);
const nodes=L.layerGroup(),sources=L.layerGroup();
// HTML labels contain only trusted constant key symbols, never source HTML.
const restrictionGroup=L.layerGroup([groups.restricted,restrictionSymbols]).addTo(map);
L.control.layers(null,{
  '<span class="key-line walkway-key"></span> Walkways':groups.walkways,
  '<span class="building-key"></span> Buildings':groups.buildings,
  '<span class="delivery-symbol">1</span> Delivery points':groups.delivery,
  '<span class="restriction-symbol"></span> Restrictions (OSM access tags)':restrictionGroup
},{collapsed:false,position:'topright'}).addTo(map);
L.control.layers(null,{
  '<span class="key-line outbound-key"></span> Outbound route':outbound,
  '<span class="key-line return-key"></span> Return to base':returning
},{collapsed:false,position:'topright'}).addTo(map);
L.control.layers({'OpenStreetMap background':tiles,'Offline GIS background':L.layerGroup()},{
  'Weighted crowd heat (active inputs)':heat,'Routing-node crowd scores':nodes,
  'Crowd source details':sources,'Published project areas':projectAreas,
  'Reported closures / planning exclusions':closures,'Software robot':robot
},{collapsed:true,position:'bottomleft'}).addTo(map);
// Pan/zoom choices persist; polling never replaces the map or its layer control.
const latlngs = coords => coords.map(([x,y])=>[y,x]);
function fitRoute(){
  const points=state?.outbound.length?latlngs(state.outbound):[robot.getLatLng()];
  map.fitBounds(L.latLngBounds(points).pad(.2),{maxZoom:17});
}
function show(s){
  state=s;received=Date.now();failed=false;
  $('phase').textContent=(s.running?'Moving · ':'Paused · ')+s.phase;
  $('route-status').textContent='Software robot: '+s.phase+' · '+s.stop.name+' · '+s.total_meters+' m round trip · outbound purple / return orange dashed.';
  if(s.phase==='complete')$('phase').textContent='Complete · back at base';
  if(s.phase==='unavailable')$('phase').textContent='No valid route';
  $('eta-label').textContent=`ETA to ${s.eta_target} · ${s.rate}× demo clock`;
  const seconds=Math.ceil(s.eta_seconds || 0);
  $('eta').textContent=s.eta_seconds===null?'Unavailable':s.phase==='complete'?'Arrived':
    `${Math.floor(seconds/60)}m ${seconds%60}s${!s.running?' (paused)':''}`;
  $('distance').textContent=`${s.traveled_meters} / ${s.total_meters} m`;
  $('notice').classList.toggle('error',s.phase==='unavailable');
  $('notice').textContent=`${s.message} ${s.rate===10?'10× playback; ETA is accelerated demo time.':''}`;
  robot.setLatLng([s.coordinates[1],s.coordinates[0]]);
  if($('follow').checked) map.panTo(robot.getLatLng());
  if(s.revision!==revision) {
    revision=s.revision;
    outbound.setLatLngs(latlngs(s.outbound));returning.setLatLngs(latlngs(s.return_route));returning.bringToFront();
    outbound.bindTooltip(text('Outbound · '+s.stop.name+' · purple'));returning.bindTooltip(text('Return to Southside Dining · orange dashed'));
    closures.clearLayers();nodes.clearLayers();sources.clearLayers();
    for(const b of s.blocked)L.polyline(latlngs(b.coordinates),{color:'#f00',weight:10}).bindPopup(text('Reported closure or conservative planning exclusion; inspect source details')).addTo(closures);
    for(const b of (s.forecast_return_blocked || []))L.polyline(latlngs(b.coordinates),{color:'#d97706',weight:9,dashArray:'4 5'}).bindPopup(text('SIMULATED forecast closure on return leg')).addTo(closures);
    for(const n of s.weighted_nodes)L.circleMarker([n.coordinates[1],n.coordinates[0]],{radius:4,color:`hsl(${120*(1-n.score)},90%,35%)`,fillOpacity:.8}).bindPopup(text(`Routing node ${n.node_id} · crowd score ${n.score} · NO separate node cost`)).addTo(nodes);
    for(const p of s.weighted_points)L.circleMarker([p.lat,p.lon],{radius:7,color:'#9a3412',fillOpacity:.7}).bindPopup(text(`${p.name} · intensity ${p.weight} × confidence ${p.confidence} · effective ${p.effective_weight.toFixed(3)} · source ${p.source} · updated ${p.updated_at} · ${p.half_life_minutes} min freshness half-life`)).addTo(sources);
    heat.setPoints(s.weighted_points);
    projectAreas.clearLayers();if(s.projects)projectAreas.addData(s.projects);

    $('stop').value=s.stop.id;$('scenario').value=s.scenario;$('rate').value=String(s.rate);
  }
  const sourceBox=document.getElementById('public-sources');
  sourceBox.replaceChildren();
  for(const [name,source] of Object.entries(s.sources||{})){
    const p=document.createElement('p');p.textContent=name+': '+(source.fresh?'CONNECTED':'UNAVAILABLE / STALE')+' · fetched '+(source.fetched_at||'never')+(source.error?' · '+source.error:'');sourceBox.appendChild(p);
  }
  for(const event of (s.events||[])){const p=document.createElement('p');p.textContent=event.title+' · '+event.location+' · '+new Date(event.starts_at).toLocaleString('en-US',{timeZone:'America/New_York'})+' to '+new Date(event.ends_at).toLocaleString('en-US',{timeZone:'America/New_York'})+' Eastern'+' · published schedule, not measured crowd';sourceBox.appendChild(p);}
  const policy=document.createElement('p');policy.textContent='Conservative Construction-area avoidance: '+s.project_excluded_edges+' graph segments excluded. These published footprints are not a complete confirmed-closure inventory.';sourceBox.appendChild(policy);
  const active=document.createElement('p');active.textContent='Weighted heat: '+s.weighted_points.length+' active sources; '+s.weighted_nodes.length+' scored routing nodes. Future events appear only during their published time windows.';sourceBox.appendChild(active);
  const note=document.createElement('p');note.textContent=s.crowd_note||'';sourceBox.appendChild(note);
  // Heat stays at the scenario's planning snapshot so it agrees with route costs.
  $('start').disabled=!s.outbound.length || s.phase==='complete' || !['projects','events'].every(k=>s.sources?.[k]?.fresh);
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
$('fit-campus').onclick=()=>map.setView([38.831,-77.307],16);
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
    for(const f of layers.features){
      const k=f.properties?.layer;
      if(groups[k]){groups[k].addData(f);counts[k]++;}
      if(k==='restricted' && f.geometry.type==='LineString'){
        const coords=f.geometry.coordinates,xy=coords[Math.floor(coords.length/2)];
        L.marker([xy[1],xy[0]],{icon:L.divIcon({className:'map-point-icon restriction-map-icon',html:'<i class="restriction-symbol"></i>',iconSize:[18,18],iconAnchor:[9,9]})})
          .bindPopup(text('OSM '+f.properties.osm_id+' · '+Object.entries(f.properties.access_tags||{}).map(([k,v])=>k+'='+v).join(', ')+' · access limitation, not a verified construction closure')).addTo(restrictionSymbols);
      }
    }
    for(const stop of config.stops){
      const option=document.createElement('option');option.value=stop.id;option.textContent=stop.name;$('stop').appendChild(option);
      L.marker([stop.coordinates[1],stop.coordinates[0]],{icon:L.divIcon({className:'map-point-icon',html:'<span class="delivery-symbol">'+stop.id+'</span>',iconSize:[24,24],iconAnchor:[12,12]})})
        .bindTooltip(text(stop.id+' · '+stop.name),{permanent:false,direction:'right',className:'delivery-name',offset:[10,0]})
        .bindPopup(text(stop.name+' · OSM building '+stop.osm_building_id+' · path coordinates '+stop.coordinates.join(', ')+' · '+stop.snap_meters+'m from source footprint · planned software delivery target'))
        .addTo(groups.delivery);counts.delivery++;
    }
    L.marker([config.base[1],config.base[0]],{icon:L.divIcon({className:'map-point-icon',html:'<span class="base-symbol">B</span>',iconSize:[24,24],iconAnchor:[12,12]})}).bindTooltip(text('Base · '+(config.base_place?.name||'Southside Dining'))).addTo(map);
    $('counts').textContent=Object.entries(counts).map(([k,v])=>`${k}: ${v}`).join(' | ');
    $('source').textContent=config.source+'. '+config.building_note;
    $('delivery-list').textContent='Base: '+config.base_place.name+' · '+config.stops.map(p=>p.id+': '+p.name).join(' | ');
    await fetchState();if(!state)throw new Error('No initial state');map.setView([38.831,-77.307],16);
    for(const id of ['stop','apply','pause','reset','fit'])$(id).disabled=false;
    schedule();
  }catch(e){error(e);}
})();
