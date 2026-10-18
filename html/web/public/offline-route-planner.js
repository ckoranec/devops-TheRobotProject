/* Route preview only. Real route verification remains in Python. */
(async function(){
  'use strict'; const $=id=>document.getElementById(id), core=MaxByteOfflineRouting;
  const map=L.map('map',{preferCanvas:true}).setView([38.83,-77.31],15);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map);
  const message=$('message'), inspector=$('inspect');
  let network,pickup=null,destination=null,result=null,choice='pickup',routeLine=null;
  const markers={};
  function download(value){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='max-byte-route-request.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}
  function report(){
    if(!result) return;
    const speed=Number($('speed').value);
    if(!Number.isFinite(speed)||speed<=0||speed>15){message.textContent='Enter a speed greater than zero and no more than 15 mph.';$('export').disabled=true;return;}
    $('export').disabled=false;
    $('route-info').textContent=JSON.stringify({distance_m:Math.round(result.meters),travel_minutes_at_selected_speed:+(result.meters/(speed*.44704)/60).toFixed(1),speed_mph:speed,pickup_node:pickup.id,destination_node:destination.id,pickup_snap_m:+pickup.distance.toFixed(1),destination_snap_m:+destination.distance.toFixed(1),notice:'Travel estimate only; meal preparation is additional. Public foot access is not robot approval.'},null,2);
  }
  function calculate(){
    result=null;$('export').disabled=true;
    if(routeLine){routeLine.remove();routeLine=null;}
    if(!pickup||!destination) return;
    try{result=core.dijkstra(network,pickup.id,destination.id);routeLine=L.polyline(result.line,{color:'#f4cc40',weight:7}).addTo(map);map.fitBounds(routeLine.getBounds(),{padding:[25,25]});message.textContent='Shortest connected preview route found. Export the request for independent Python verification.';report();}
    catch(error){message.textContent=error.message;$('route-info').textContent='No route preview. Choose endpoints on the same connected network.';}
  }
  $('pickup').onclick=()=>{choice='pickup';message.textContent='Click the intended pickup location.';};
  $('destination').onclick=()=>{choice='destination';message.textContent='Click the intended destination; do not substitute an arbitrary longer loop.';};
  $('clear').onclick=()=>{pickup=destination=result=null;choice='pickup';for(const m of Object.values(markers))m.remove();if(routeLine)routeLine.remove();routeLine=null;$('export').disabled=true;$('route-info').textContent='Select pickup and destination.';message.textContent='Ready to choose pickup.';};
  $('speed').oninput=report;
  $('export').onclick=()=>{if(!result)return;download({schema:'max-byte-route-request-v1',map_sha256:network.map_sha256,pickup:pickup.point,destination:destination.point,max_snap_m:35,speed_mph:Number($('speed').value)});};
  function choose(event){
    if(drawing){addDraftPoint(event.latlng);return;}
    if(!network)return;
    try{const snapped=core.nearest(network,[event.latlng.lat,event.latlng.lng],35);if(markers[choice])markers[choice].remove();const label=choice==='pickup'?'Pickup':'Destination';markers[choice]=L.marker(network.nodes[snapped.id]).addTo(map).bindPopup(label+' · node '+snapped.id);if(choice==='pickup'){pickup=snapped;choice='destination';message.textContent='Pickup selected. Now click the destination.';}else{destination=snapped;message.textContent='Destination selected.';}calculate();}
    catch(error){message.textContent=error.message;}
  }
  // Author draft missing features without changing the downloaded graph.
  let drawing=null, draftPoints=[], draftSketch=null;
  const drafts=[], draftLayer=L.layerGroup().addTo(map);
  function addDraftPoint(ll){
    draftPoints.push([ll.lng,ll.lat]);
    if(draftSketch)draftSketch.remove();
    draftSketch=L.polyline(draftPoints.map(p=>[p[1],p[0]]),{color:'#e879f9',dashArray:'4 5'}).addTo(map);
    $('draft-status').textContent=draftPoints.length+' draft point(s). Use Finish feature when ready.';
    if(['entrance','delivery_point'].includes(drawing)) finishDraft();
  }
  function finishDraft(){
    if(!drawing)return;
    const point=['entrance','delivery_point'].includes(drawing), line=drawing==='path';
    if(draftPoints.length<(point?1:line?2:3)){$('draft-status').textContent='Add more vertices before finishing.';return;}
    const coordinates=point?draftPoints[0]:line?draftPoints:[...draftPoints,draftPoints[0]];
    const feature={type:'Feature',properties:{id:'draft-'+(drafts.length+1),type:drawing,source:'manual draft drawn in MAX Byte workspace',review_status:'unverified',robot_navigation_approved:false},geometry:{type:point?'Point':line?'LineString':'Polygon',coordinates:point||line?coordinates:[coordinates]}};
    drafts.push(feature);
    L.geoJSON(feature,{style:{color:'#e879f9',weight:4,fillOpacity:.15},pointToLayer:(_f,ll)=>L.circleMarker(ll,{radius:8,color:'#e879f9'}),onEachFeature:(f,l)=>l.on('click',()=>{inspector.textContent=JSON.stringify(f.properties,null,2);})}).addTo(draftLayer);
    if(draftSketch)draftSketch.remove();draftSketch=null;drawing=null;draftPoints=[];
    $('draft-status').textContent=drafts.length+' draft feature(s). Export before closing. Graph is unchanged.';
  }
  $('draft-start').onclick=()=>{if(draftSketch)draftSketch.remove();draftSketch=null;draftPoints=[];drawing=$('draft-type').value;$('draft-status').textContent='Click map vertices for '+drawing+'. Use Finish feature or Cancel drawing.';};
  $('draft-finish').onclick=finishDraft;
  $('draft-cancel').onclick=()=>{if(draftSketch)draftSketch.remove();draftSketch=null;drawing=null;draftPoints=[];$('draft-status').textContent='Drawing cancelled. Existing completed drafts retained.';};
  $('draft-export').onclick=()=>{if(!drafts.length){$('draft-status').textContent='No completed draft features to export.';return;}const url=URL.createObjectURL(new Blob([JSON.stringify({type:'FeatureCollection',features:drafts},null,2)],{type:'application/geo+json'}));const a=document.createElement('a');a.href=url;a.download='max-byte-manual-drafts.geojson';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);};
  map.on('click',choose);
  try{
    const response=await fetch('data/offline-network.json');if(!response.ok)throw Error('Network HTTP '+response.status);network=await response.json();
    if(!network.nodes||!network.adj||!network.features)throw Error('Invalid offline network file');
    const styles={paths:'#4ade80',roads:'#94a3b8',restrictions:'#f87171',closures:'#fb923c',buildings:'#a78bfa',entrances:'#38bdf8',delivery_points:'#facc15',routing_nodes:'#22d3ee'};
    const groups={};for(const key of Object.keys(styles))groups[key]=L.layerGroup();
    for(const feature of network.features){
      const key=feature.properties.layer;if(!groups[key])continue;
      const layer=L.geoJSON(feature,{style:{color:styles[key],weight:3,fillOpacity:.15},pointToLayer:(_f,ll)=>L.circleMarker(ll,{radius:5,color:styles[key]}),onEachFeature:(f,l)=>l.on('click',event=>{inspector.textContent=JSON.stringify(f.properties,null,2);if(event.originalEvent)L.DomEvent.stopPropagation(event.originalEvent);})});layer.addTo(groups[key]);
    }
    for(const [id,ll] of Object.entries(network.nodes)) L.circleMarker(ll,{radius:3,color:styles.routing_nodes,weight:1,fillOpacity:.8}).on('click',event=>{if(event.originalEvent)L.DomEvent.stopPropagation(event.originalEvent);choose(event);}).addTo(groups.routing_nodes);
    for(const [key,group] of Object.entries(groups)){
      const count=key==='routing_nodes'?Object.keys(network.nodes).length:network.features.filter(f=>f.properties.layer===key).length;
      const input=document.createElement('input');input.type='checkbox';input.checked=count>0;input.disabled=count===0;if(count)group.addTo(map);
      input.onchange=()=>input.checked?group.addTo(map):group.remove();const label=document.createElement('label');label.append(input,document.createTextNode(key.replaceAll('_',' ')+' ('+count+')'));$('layers').append(label);
    }
    const coordinates=Object.values(network.nodes);if(coordinates.length)map.fitBounds(coordinates,{padding:[20,20],maxZoom:16});
    $('coverage').textContent='Source '+network.source+' · '+network.source_timestamp+' · '+network.components.length+' components. Buildings and entrances remain unavailable when absent from the source. Geometric crossings without shared OSM node IDs are not joined.';

    // Preload the user's required out-and-return mission, generated by Python.
    const mr=await fetch('data/mission-route.json',{cache:'no-store'});
    if(!mr.ok)throw Error('Required mission HTTP '+mr.status);
    const mission=await mr.json(),meta=mission.metadata;
    pickup=core.nearest(network,meta.pickup,35);
    destination=core.nearest(network,meta.destination,35);
    markers.pickup=L.marker(network.nodes[pickup.id]).addTo(map).bindPopup(meta.pickup_name);
    markers.destination=L.marker(network.nodes[destination.id]).addTo(map).bindPopup(meta.destination_name);
    L.geoJSON(mission,{style:{color:'#a78bfa',weight:7,opacity:.5}}).addTo(map);
    calculate();
    message.textContent='Required mission loaded: Horizon Hall → 4504 Overcup Court → Horizon Hall. Yellow = outbound preview; purple = complete Python mission.';
    $('route-info').textContent+='\n\nPython mission: '+(meta.outbound_m/1000).toFixed(2)+' km outbound, '+(meta.return_m/1000).toFixed(2)+' km return, '+(meta.total_m/1000).toFixed(2)+' km total.\nEndpoint snaps: '+meta.pickup_snap_m.toFixed(1)+' m / '+meta.destination_snap_m.toFixed(1)+' m.\nSimulation only; road robot access requires review.';

  }catch(error){message.textContent='Unable to load workspace: '+error.message;}
  new ResizeObserver(()=>map.invalidateSize({pan:false})).observe($('map'));
})();
