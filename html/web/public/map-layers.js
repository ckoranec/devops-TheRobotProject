/* Shared GIS layers for all three maps. Displaying a road is not robot approval. */
window.maxByteBuildLayers=async function(map,_oldDemoData){
  'use strict';
  const host=document.getElementById('gmu-campus-map');if(!host||document.getElementById('mb-gis-controls'))return;
  const panel=document.createElement('section');panel.id='mb-gis-controls';panel.setAttribute('aria-label','GIS layers and feature details');
  panel.innerHTML='<h3>Campus GIS layers</h3><p data-source>Loading expanded local data…</p><div data-toggles></div><details><summary>Feature inspector</summary><pre data-details tabindex="0">Click a colored source feature.</pre></details><label>Preview manual drafts <input type="file" accept=".json,.geojson" data-import></label><p class="mb-mission-note">Draft imports are unverified display overlays; they never modify delivery routing.</p>';
  host.before(panel);
  try{
    const response=await fetch('data/mission-network.json',{cache:'no-store'});if(!response.ok)throw Error('GIS HTTP '+response.status);const network=await response.json();
    let attempts=0;while(!window.maxByteMaps&&attempts++<100)await new Promise(r=>setTimeout(r,50));
    if(!window.maxByteMaps)throw Error('Three map instances unavailable');
    const colors={paths:'#22c55e',roads:'#94a3b8',restrictions:'#ef4444',closures:'#f472b6',buildings:'#a78bfa',entrances:'#38bdf8',delivery_points:'#facc15',junctions:'#fb923c',manual_drafts:'#e879f9'};
    const groups={},counts={};for(const key of Object.keys(colors)){groups[key]=[];counts[key]=0;}
    for(const map of Object.values(window.maxByteMaps)){
      const renderer=L.canvas({padding:.4});
      for(const key of Object.keys(colors))groups[key].push(L.layerGroup().addTo(map));
      for(const feature of network.features){
        const key=feature.properties.layer;if(!groups[key])continue;
        const index=Object.values(window.maxByteMaps).indexOf(map);
        L.geoJSON(feature,{renderer,style:{renderer,color:colors[key],weight:key==='restrictions'?5:3,opacity:.7,fillOpacity:.12},pointToLayer:(_f,ll)=>L.circleMarker(ll,{renderer,radius:6,color:colors[key]}),onEachFeature:(f,layer)=>layer.on('click',()=>{panel.querySelector('[data-details]').textContent=JSON.stringify(f.properties,null,2);panel.querySelector('details').open=true;})}).addTo(groups[key][index]);
      }
      const index=Object.values(window.maxByteMaps).indexOf(map);
      for(const [id,edges] of Object.entries(network.adj))if(new Set(edges.map(e=>e.to)).size>2){const ll=network.nodes[id];L.circleMarker(ll,{renderer,radius:3,color:colors.junctions}).on('click',()=>{panel.querySelector('[data-details]').textContent='Derived junction '+id+'\n'+JSON.stringify(ll);}).addTo(groups.junctions[index]);}
    }
    for(const f of network.features)if(f.properties.layer in counts)counts[f.properties.layer]++;
    counts.junctions=Object.values(network.adj).filter(edges=>new Set(edges.map(e=>e.to)).size>2).length;
    for(const [key,color] of Object.entries(colors)){
      const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=counts[key]>0&&key!=='junctions';input.disabled=!counts[key]&&key!=='manual_drafts';
      if(!input.checked)for(const group of groups[key])group.remove();
      input.onchange=()=>Object.values(window.maxByteMaps).forEach((m,i)=>input.checked?groups[key][i].addTo(m):groups[key][i].remove());
      const name=key==='delivery_points'?'Configured delivery stops':key.replaceAll('_',' ');const span=document.createElement('span');span.style.color=color;span.textContent=' '+name+' ('+counts[key]+')'+(!counts[key]?' — no source features':'');label.append(input,span);panel.querySelector('[data-toggles]').append(label);
      if(key==='manual_drafts'){panel._draftToggle=input;panel._draftCount=span;}
    }
    panel.querySelector('[data-source]').textContent='Local file: '+network.source+' · Source timestamp '+network.source_timestamp;
    document.getElementById('gmu-map-status').textContent='Expanded GIS: '+counts.paths+' paths, '+counts.roads+' roads, '+counts.restrictions+' restriction-tagged features. Route is a simulation preview; missing buildings/entrances are not fabricated.';
    panel.querySelector('[data-import]').onchange=async event=>{
      try{const file=event.target.files[0];if(!file)return;if(file.size>5*1024*1024)throw Error('Draft file exceeds 5 MB');const data=JSON.parse(await file.text());if(data.type!=='FeatureCollection'||!Array.isArray(data.features))throw Error('Expected GeoJSON FeatureCollection');
        for(const feature of data.features){if(feature.type!=='Feature'||!feature.geometry||!['Point','LineString','Polygon'].includes(feature.geometry.type))throw Error('Unsupported draft geometry');const points=feature.geometry.type==='Point'?[feature.geometry.coordinates]:feature.geometry.type==='LineString'?feature.geometry.coordinates:feature.geometry.coordinates.flat();if(!points.length||points.some(p=>!Array.isArray(p)||p.length<2||!Number.isFinite(p[0])||!Number.isFinite(p[1])||Math.abs(p[0])>180||Math.abs(p[1])>90))throw Error('Invalid draft coordinates');}
        groups.manual_drafts.forEach(g=>g.clearLayers());Object.values(window.maxByteMaps).forEach((m,i)=>{L.geoJSON(data,{style:{color:'#e879f9',weight:4,fillOpacity:.15},pointToLayer:(_f,ll)=>L.circleMarker(ll,{radius:7,color:'#e879f9'}),onEachFeature:(f,l)=>l.on('click',()=>{panel.querySelector('[data-details]').textContent='UNVERIFIED MANUAL DRAFT\n'+JSON.stringify(f.properties||{},null,2);panel.querySelector('details').open=true;})}).addTo(groups.manual_drafts[i]);groups.manual_drafts[i].addTo(m);});panel._draftToggle.checked=true;panel._draftCount.textContent=' manual drafts ('+data.features.length+') — unverified';panel.querySelector('[data-details]').textContent=data.features.length+' manual draft feature(s) shown. Route graph unchanged. Import again after refresh.';
      }catch(error){panel.querySelector('[data-details]').textContent='Draft import failed: '+error.message;panel.querySelector('details').open=true;}
    };
    window.dispatchEvent(new Event('maxbyte:layers'));
  }catch(error){panel.querySelector('[data-source]').textContent='GIS unavailable: '+error.message;console.error(error);}
};
