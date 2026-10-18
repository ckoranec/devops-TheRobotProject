/* Game motion follows existing GIS edges; these are simulation lanes, not robot permissions. */
(function(root){'use strict';
function path(graph,start,goal){const q=[start],prev=new Map([[start,null]]);for(let i=0;i<q.length&&!prev.has(goal);i++)for(const n of graph.nodes[q[i]].links)if(!prev.has(n)){prev.set(n,q[i]);q.push(n);}if(!prev.has(goal))return [];const p=[goal];while(p[0]!==start)p.unshift(prev.get(p[0]));return p.slice(1);}
function nextDirection(graph,node,dir){const v={up:[0,1],down:[0,-1],left:[-1,0],right:[1,0]}[dir];if(!v)return null;const a=graph.nodes[node];let score=.25,best=null;for(const id of a.links){const b=graph.nodes[id],dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy),s=(dx*v[0]+dy*v[1])/d;if(s>score){score=s;best=id;}}return best;}
function advance(graph,e,meters,choose){let guard=0;while(meters>0&&guard++<200){if(!e.to){e.to=choose(e);if(!e.to)break;e.travel=0;}const a=graph.nodes[e.node],b=graph.nodes[e.to],length=Math.hypot(b.x-a.x,b.y-a.y),step=Math.min(meters,length-e.travel);e.travel+=step;meters-=step;if(e.travel>=length-1e-7){e.node=e.to;e.to=null;e.travel=0;}else break;}const a=graph.nodes[e.node],b=e.to?graph.nodes[e.to]:a,t=e.to?e.travel/Math.hypot(b.x-a.x,b.y-a.y):0;e.xy=[a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t];e.ll=[a.ll[0]+(b.ll[0]-a.ll[0])*t,a.ll[1]+(b.ll[1]-a.ll[1])*t];}
function deadlineReached(state){return Boolean(state&&(state.deliveryArrived||state.distanceM>=state.outboundM));}
function canWin(caught,state){return caught===5&&Boolean(state)&&!deadlineReached(state);}
const api={path,nextDirection,advance,deadlineReached,canWin};root.MaxByteNaturalGame=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
