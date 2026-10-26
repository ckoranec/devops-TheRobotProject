"use strict";
// DAVID: persistent map and source/age/ETA UI. SHEK: live-report API adapter.
// No timer generates coordinates or decrements an ETA without a new observation.
const el=id=>document.getElementById(id);
const liveMap=L.map('campus-map').setView([38.831,-77.307],16);
const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'});
const groups={},plain=value=>{const s=document.createElement('span');s.textContent=value;return s;};
for(const [kind,color] of Object.entries({walkways:'#15803d',buildings:'#2563eb',restricted:'#dc2626'})){
 groups[kind]=L.geoJSON(null,{style:{color,weight:3,fillOpacity:.25},onEachFeature:(f,l)=>{l.bindTooltip(plain(f.properties.name+' · OSM '+f.properties.osm_id),{sticky:true});}}).addTo(liveMap);
}
const places=L.layerGroup().addTo(liveMap),closures=L.layerGroup().addTo(liveMap),sourceMarkers=L.layerGroup(),nodeMarkers=L.layerGroup();
const outbound=L.polyline([],{color:'#7e22ce',weight:6}).addTo(liveMap),returning=L.polyline([],{color:'#007c91',dashArray:'7 8',weight:3}).addTo(liveMap);
const heat=new WeightedHeatLayer().addTo(liveMap),positionLayer=L.layerGroup().addTo(liveMap);
let positionMarker=null,chosen=null,chosenMarker=null,graph=[],state=null,pollTimer=null,loading=false;
const reverse=xy=>[xy[1],xy[0]];
L.control.layers({'Offline GIS':L.layerGroup().addTo(liveMap),'Online OSM tiles':tiles},{'Paths':groups.walkways,'Buildings':groups.buildings,'OSM access restrictions':groups.restricted,'Verified delivery places':places,'Staff-reported closures':closures,'Actual reported position':positionLayer,'Estimated route':outbound,'Planned return':returning,'Current crowd heat':heat,'Crowd report details':sourceMarkers,'Routing-node crowd scores':nodeMarkers},{collapsed:true}).addTo(liveMap);
for(let i=1;i<=6;i++)for(const id of ['destination','slot']){const o=document.createElement('option');o.value=String(i);o.textContent='Delivery '+i;el(id).appendChild(o);}
L.control.scale({imperial:false}).addTo(liveMap);
async function request(url,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
 try{
  const r=await fetch(url,{signal:controller.signal,cache:'no-store',...(body?{method:'POST',headers:{'Content-Type':'application/json','X-Operator-Key':el('key').value},body:JSON.stringify(body)}:{})});
  const x=await r.json();if(!r.ok)throw Error(x.error||r.status);return x;
 }finally{clearTimeout(timer);}
}
function draw(s){
 state=s;el('notice').classList.toggle('error',!s.position_fresh);
 el('notice').textContent=s.closure_coverage+'. Crowd coverage: '+s.crowd_coverage+'. No hardware telemetry.';
 el('location-status').textContent=!s.position?'No position received':s.position_fresh?'Staff report · '+s.position.source:'STALE staff report';
 el('coverage').textContent=s.crowd_coverage;
 el('eta').textContent=s.trip.eta_seconds==null?'Unavailable':Math.ceil(s.trip.eta_seconds/60)+' min · model estimate';
 outbound.setLatLngs(s.trip.status==='available'?s.trip.coordinates.map(reverse):[]);
 const trip=s.routes.find(r=>r.id===el('destination').value);
 returning.setLatLngs(trip?.status==='available'?trip.return_route.coordinates.map(reverse):[]);
 if(s.position){
  const ll=reverse(s.position.coordinates);
  if(!positionMarker)positionMarker=L.circleMarker(ll,{radius:9,fillOpacity:1}).addTo(positionLayer);
  positionMarker.setLatLng(ll).setStyle({color:s.position_fresh?'#172b3a':'#777'});
  positionMarker.bindPopup(plain('STAFF-TEST-01 · '+s.position.source+' · observed '+s.position.observed_at+' · map-reported, not GPS'));
  if(el('follow').checked)liveMap.panTo(ll);
 }
 places.clearLayers();for(const p of Object.values(s.places))L.circleMarker(reverse(p.coordinates),{radius:7,color:p.slot==='base'?'#172b3a':'#800030',fillOpacity:1}).bindTooltip(plain(p.name+' · verified by '+p.source+' · snap '+p.snap_meters+'m')).addTo(places);
 closures.clearLayers();for(const b of s.blocked)L.polyline(b.coordinates.map(reverse),{color:'#f00',weight:9}).bindPopup(plain('Staff-reported closure '+b.id)).addTo(closures);
 sourceMarkers.clearLayers();for(const p of s.weighted_points)L.circleMarker([p.lat,p.lon],{radius:7,color:'#9a3412'}).bindPopup(plain(p.name+' · '+p.source+' · intensity '+p.weight+' × confidence '+p.confidence+' · updated '+p.updated_at)).addTo(sourceMarkers);
 nodeMarkers.clearLayers();for(const n of s.weighted_nodes)L.circleMarker(reverse(n.coordinates),{radius:4,color:`hsl(${120*(1-n.score)},90%,35%)`}).bindPopup(plain('Node '+n.node_id+' · score '+n.score+' · no additional node charge')).addTo(nodeMarkers);
 heat.setPoints(s.weighted_points);
 const previous=el('closure-id').value;el('closure-id').replaceChildren();
 for(const c of s.closures.filter(c=>c.status==='confirmed')){const o=document.createElement('option');o.value=c.id;o.textContent=c.id+' · '+c.source+(c.review_overdue?' · REVIEW OVERDUE':'');el('closure-id').appendChild(o);}
 if([...el('closure-id').options].some(o=>o.value===previous))el('closure-id').value=previous;
 el('routes').replaceChildren();for(const r of s.routes){const p=document.createElement('p');p.textContent=r.id+'. '+r.name+' — '+r.status+' — '+(r.status==='available'?r.outbound.meters+'m outward / '+r.return_route.meters+'m return. '+r.reason:r.reason);el('routes').appendChild(p);}
}
async function refresh(){if(loading)return;loading=true;try{draw(await request('/api/live/state?stop='+el('destination').value+'&leg='+el('leg').value));}catch(e){el('notice').classList.add('error');el('notice').textContent='Connection failed; observations may be stale. '+e.message;el('eta').textContent='Unavailable';outbound.setLatLngs([]);}finally{loading=false;}}
function schedule(){clearTimeout(pollTimer);pollTimer=setTimeout(async()=>{await refresh();schedule();},Number(el('cadence').value));}
for(const id of ['cadence','destination','leg'])el(id).onchange=async()=>{await refresh();schedule();};
// Pick a graph segment by geometric proximity, not by invented OSM identifiers.
function segmentDistance(point,line){
 const p=liveMap.project(reverse(point),18),a=liveMap.project(reverse(line[0]),18),b=liveMap.project(reverse(line[1]),18);
 const dx=b.x-a.x,dy=b.y-a.y,t=Math.max(0,Math.min(1,((p.x-a.x)*dx+(p.y-a.y)*dy)/(dx*dx+dy*dy||1)));
 return liveMap.distance(reverse(point),liveMap.unproject(L.point(a.x+t*dx,a.y+t*dy),18));
}
liveMap.on('click',e=>{chosen=[e.latlng.lng,e.latlng.lat];if(chosenMarker)chosenMarker.setLatLng(e.latlng);else chosenMarker=L.circleMarker(e.latlng,{radius:6,color:'#111',dashArray:'2 2'}).addTo(liveMap);el('selection').textContent='Selected longitude/latitude: '+chosen.join(', ');});
el('submit').onclick=async()=>{
 try{
  if(!chosen)throw Error('Click the actual location on the map first');
  if(!el('verified').checked)throw Error('Confirm this is an actual observation/place, not practice data');
  const common={coordinates:chosen,source:el('reporter').value};let endpoint,body;
  switch(el('kind').value){
   case 'position':endpoint='position';body={...common,observed_at:new Date().toISOString()};break;
   case 'place':endpoint='place';body={...common,slot:el('slot').value,name:el('name').value,verified:true};break;
   case 'crowd':endpoint='crowd';body={...common,id:el('observation-id').value,name:el('name').value,weight:Number(el('weight').value),confidence:Number(el('confidence').value),radius_m:Number(el('radius').value)};break;
   case 'closure':{
    endpoint='closure';let nearest=null,d=Infinity;for(const edge of graph){const value=segmentDistance(chosen,edge.coordinates);if(value<d){nearest=edge;d=value;}}
    if(d>20)throw Error('Click within 20m of the actual blocked walkway segment');
    body={id:'closure-'+Date.now(),status:'confirmed',edge_ids:[nearest.id],source:common.source};break;
   }
  }
  await request('/api/live/'+endpoint,body);el('report-result').textContent='Actual staff report accepted at '+new Date().toLocaleTimeString();el('verified').checked=false;await refresh();
 }catch(e){el('report-result').textContent=e.message;}
};
el('clear').onclick=async()=>{try{if(!el('verified').checked)throw Error('Confirm you observed that the closure has cleared');const c=state.closures.find(x=>x.id===el('closure-id').value);if(!c)throw Error('Choose an active closure');await request('/api/live/closure',{...c,status:'cleared',source:el('reporter').value});el('report-result').textContent='Explicit clearance recorded';await refresh();}catch(e){el('report-result').textContent=e.message;}};
el('fit').onclick=()=>liveMap.setView([38.831,-77.307],16);
setInterval(()=>{if(!state?.position)return;const age=Math.max(0,(Date.now()-Date.parse(state.position.observed_at))/1000);el('age').textContent=Math.floor(age)+'s'+(age>30?' · STALE':'');if(age>30){el('eta').textContent='Unavailable · stale position';outbound.setLatLngs([]);positionMarker?.setStyle({color:'#777'});}},500);
(async()=>{try{const [config,layers,edges]=await Promise.all([request('/api/live/config'),request('/api/live/layers'),request('/api/live/graph')]);graph=edges;for(const f of layers.features)groups[f.properties.layer]?.addData(f);el('source').textContent='OSM snapshot retrieved '+(config.source.retrieved_at||'previously')+' · '+(config.source.building_count||'bundled')+' building outlines. Geometry is not a live obstacle feed.';await refresh();schedule();}catch(e){el('notice').textContent='Startup failed: '+e.message;}})();
