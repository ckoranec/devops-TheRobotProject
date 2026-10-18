/* MAX BYTE SHARED MISSION V1 — simulated telemetry, not hardware control.
   Python Dijkstra generates mission-route.json from the existing GIS dataset. */
'use strict';
(async function(){
  const core=MaxByteMissionCore,map=campusMap,host=document.getElementById('gmu-campus-map');
  const panel=document.createElement('section');panel.id='robot-control-panel';panel.setAttribute('aria-label','Simulated delivery controls');
  panel.innerHTML=`<h3>MAX Byte · Delivery and return</h3><p><strong>SIMULATION · Python Dijkstra route</strong></p><p>Horizon Hall → 4504 Overcup Court → Horizon Hall</p><div class="mb-mission-buttons"><button id="robot-start" type="button">Start</button><button id="robot-pause" type="button">Pause</button><button id="robot-reset" type="button">Reset</button><button id="robot-fit" type="button">Fit route</button><button id="robot-center" type="button">Center robot</button></div><label for="robot-preview-speed">Simulation speed</label> <select id="robot-preview-speed"><option value="3">3 mph</option><option value="6">6 mph</option><option value="10">10 mph</option><option value="15" selected>15 mph maximum</option></select><div id="robot-simulation-status" aria-live="polite">Loading verified route geometry…</div><p class="mb-mission-note">Road access requires review before real-robot operation. Times below exclude meal preparation.</p>`;
  host.after(panel);const $=id=>document.getElementById(id),status=$('robot-simulation-status');
  try{
    // V30: an explicit, owner-checked mission URL replaces only this browser's mission.
    const selected=new URLSearchParams(location.search).get('mission');
    let mission;
    if(selected){
      if(!/^[0-9a-f-]{36}$/i.test(selected))throw Error('Invalid customer mission link');
      const response=await fetch('/api/customer/missions/'+encodeURIComponent(selected),{credentials:'same-origin',cache:'no-store'});
      const result=await response.json();if(!response.ok)throw Error(result.error||'Customer mission unavailable');
      mission=result.mission;window.maxByteCustomerMissionId=result.mission_id;
    }else{
      const response=await fetch('data/mission-route.json',{cache:'no-store'});if(!response.ok)throw Error('Mission HTTP '+response.status);mission=await response.json();
    }
    const destination=mission.metadata?.destination_name||'4504 Overcup Court';
    const safeText=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const updateLabels=()=>{const desc=document.getElementById('mb-mode-desc');if(desc)desc.textContent='Horizon Hall → '+destination+' → Horizon Hall';};
    window.addEventListener('maxbyte:mode',updateLabels);updateLabels();
    const route=core.prepare(mission.features);let distance=0,state='Ready',speed=15,last=null,frame=null,lastPublish=0,purchaseClock=null;
    const icon=maxByteRobotIcon('#a855f7',44,'Delivery robot');
    const robot=L.marker(route.line[0],{icon}).addTo(map);window.maxByteDeliveryRobot=robot;
    const line=L.polyline(route.line,{opacity:0,interactive:false});maxByteDrawMission(map,mission);
    L.circleMarker(route.line[0],{radius:8,color:'#2563eb',fillOpacity:1}).addTo(map).bindPopup('Horizon Hall · start and return');
    L.circleMarker(core.atDistance(route,route.outbound),{radius:8,color:'#22c55e',fillOpacity:1}).addTo(map).bindPopup(Object.assign(document.createElement('span'),{textContent:destination+' · snapped delivery node'}));
    function publish(){
      const arrived=distance>=route.outbound-.001,mps=speed*.44704,leg=distance>=route.total?'Returned to Horizon Hall':arrived?'Returning to Horizon Hall':'Delivering to '+safeText(destination);
      const snapshot={simulated:true,state,leg,speedMph:speed,distanceM:distance,totalM:route.total,outboundM:route.outbound,deliveryArrived:arrived,deliveryEtaSeconds:Math.max(0,route.outbound-distance)/mps,returnEtaSeconds:Math.max(0,route.total-distance)/mps,position:robot.getLatLng(),timestamp:new Date().toISOString()};
      window.maxByteDeliveryState=snapshot;window.dispatchEvent(new CustomEvent('maxbyte:state',{detail:snapshot}));
      status.innerHTML=`<p><strong>${state}</strong> · ${leg}</p><p>Delivery leg ${(route.outbound/1000).toFixed(2)} km · Round trip ${(route.total/1000).toFixed(2)} km</p><p>Delivery ETA ${arrived?'arrived':(snapshot.deliveryEtaSeconds/60).toFixed(1)+' min'} · Return ETA ${(snapshot.returnEtaSeconds/60).toFixed(1)} min</p><p>Progress ${(distance/route.total*100).toFixed(1)}% · ${speed} mph · Continuous animation</p>`;
    }
    function stop(){if(frame!==null)cancelAnimationFrame(frame);frame=null;last=null;}
    function animate(now){if(state!=='En route')return;if(last===null)last=now;const dt=Math.max(0,(now-last)/1000);last=now;distance=purchaseClock?Math.min(route.total,Math.max(0,purchaseClock.elapsed+(performance.now()-purchaseClock.anchor)/1000)*15*.44704):Math.min(route.total,distance+speed*.44704*dt);robot.setLatLng(core.atDistance(route,distance));if(now-lastPublish>250){publish();lastPublish=now;}if(distance>=route.total){state='Returned';stop();publish();return;}frame=requestAnimationFrame(animate);}
    function start(){if(selected&&!purchaseClock)return;if(purchaseClock&&distance>=route.total)return;if(state==='En route')return;if(state==='Returned')reset();state='En route';last=null;frame=requestAnimationFrame(animate);publish();}
    function reset(){if(purchaseClock||selected)return;stop();distance=0;state='Ready';robot.setLatLng(route.line[0]);publish();window.dispatchEvent(new Event('maxbyte:reset'));}
    $('robot-start').onclick=start;$('robot-pause').onclick=()=>{if(purchaseClock)return;if(state==='En route'){stop();state='Paused';publish();}};$('robot-reset').onclick=reset;
    $('robot-preview-speed').onchange=()=>{const value=Number($('robot-preview-speed').value);if(!purchaseClock&&value>0&&value<=15){speed=value;publish();}};
    $('robot-fit').onclick=()=>{const active=window.maxByteMaps?.[window.maxByteMode||1]||map;active.fitBounds(window.maxByteCommonBounds?.()||line.getBounds(),{padding:[35,35]});};
    $('robot-center').onclick=()=>{const active=window.maxByteMaps?.[window.maxByteMode||1]||map;active.panTo(robot.getLatLng());};
    window.maxByteMissionControl={start,reset,seek:meters=>{if(purchaseClock)return;distance=Math.max(0,Math.min(route.total,meters));robot.setLatLng(core.atDistance(route,distance));publish();},pause:()=>{if(purchaseClock)return;if(state==='En route'){stop();state='Paused';publish();}},startPurchase:clock=>{stop();purchaseClock={elapsed:Math.max(0,clock.elapsed_seconds),anchor:performance.now()};speed=15;
      distance=Math.min(route.total,purchaseClock.elapsed*15*.44704);robot.setLatLng(core.atDistance(route,distance));
      state=distance>=route.total?'Returned':'Ready';if(state!=='Returned')start();else publish();
      for(const id of ['robot-start','robot-pause','robot-reset'])$(id).disabled=true;
      $('robot-preview-speed').disabled=true;
    },getState:()=>window.maxByteDeliveryState};window.maxByteRoutePlan={mission,route};publish();window.dispatchEvent(new CustomEvent('maxbyte:mission',{detail:window.maxByteRoutePlan}));map.fitBounds(window.maxByteCommonBounds?.()||line.getBounds(),{padding:[35,35]});
  }catch(error){status.textContent='Mission unavailable: '+error.message;console.error(error);}
})();
