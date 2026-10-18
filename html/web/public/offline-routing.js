/* Pure routing helpers: coordinates are lat/lon internally, GeoJSON lon/lat. */
(function(root) {
  'use strict';
  function meters(a,b) {
    const r=x=>x*Math.PI/180, x=r(b[0]-a[0]), y=r(b[1]-a[1]);
    const h=Math.sin(x/2)**2+Math.cos(r(a[0]))*Math.cos(r(b[0]))*Math.sin(y/2)**2;
    return 12742000*Math.asin(Math.sqrt(Math.max(0,Math.min(1,h))));
  }
  function nearest(network, point, tolerance=35) {
    if(!Array.isArray(point)||point.length!==2||!point.every(Number.isFinite)||Math.abs(point[0])>90||Math.abs(point[1])>180) throw Error('Invalid coordinates');
    let id=null, distance=Infinity;
    for(const [key,ll] of Object.entries(network.nodes)) {
      const d=meters(point,ll); if(d<distance){id=key; distance=d;}
    }
    if(id===null || distance>tolerance) throw Error('No routing node within '+tolerance+' m. Click closer to a cyan routing node.');
    return {id,distance,point};
  }
  function dijkstra(network, start, goal) {
    if(!network.nodes[start]||!network.nodes[goal]) throw Error('Unknown routing endpoint');
    if(start===goal) throw Error('Select two different routing nodes.');
    const dist=new Map([[start,0]]), prev=new Map(), settled=new Set();
    // Match the team's nonnegative meter-weight Dijkstra; campus graph is small.
    const queue=new Set([start]);
    while(queue.size) {
      let node=null, best=Infinity;
      for(const id of queue) if(dist.get(id)<best){node=id;best=dist.get(id);}
      queue.delete(node); if(node===goal) break; settled.add(node);
      for(const edge of network.adj[node]||[]) {
        if(settled.has(edge.to)) continue;
        const next=best+edge.cost;
        if(next<(dist.get(edge.to)??Infinity)){dist.set(edge.to,next);prev.set(edge.to,{from:node,edge});queue.add(edge.to);}
      }
    }
    if(!prev.has(goal)) throw Error('No connected path. These endpoints are in different components or no permitted path reaches them.');
    const edges=[];let cursor=goal;
    while(cursor!==start){const step=prev.get(cursor);edges.push(step.edge);cursor=step.from;}
    edges.reverse();const line=[network.nodes[start]];
    for(const edge of edges) line.push(...edge.coords.slice(1));
    return {meters:dist.get(goal),line,ways:edges.map(e=>e.way_id)};
  }
  const api={meters,nearest,dijkstra};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;
  root.MaxByteOfflineRouting=api;
})(typeof window==='undefined'?globalThis:window);
