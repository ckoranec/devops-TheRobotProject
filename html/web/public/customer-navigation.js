/* V34: preserve the current customer mission across navigation on this origin. */
(()=>{'use strict';const current=new URL(location.href),params=current.searchParams;
let mission=params.get('mission')||'';if(!mission){try{mission=sessionStorage.getItem('max-byte-active-mission')||'';}catch(_){}}
if(!/^[0-9a-f-]{36}$/i.test(mission))mission='';
if(mission){try{sessionStorage.setItem('max-byte-active-mission',mission);}catch(_){}}
window.maxByteRememberMission=function(id){if(!/^[0-9a-f-]{36}$/i.test(id))return;mission=id;try{sessionStorage.setItem('max-byte-active-mission',id);}catch(_){}update();};
function update(){for(const a of document.querySelectorAll('a[href]')){
 const target=new URL(a.getAttribute('href'),location.href);if(target.origin!==location.origin)continue;
 const shared=a.closest('.maxx-site-header')||a.matches('[data-flow-step],a.badge');
 if(mission&&['/order.html','/tracking.html','/MapAPI.html'].includes(target.pathname)&&(shared||!target.searchParams.has('mission')))target.searchParams.set('mission',mission);
 a.href=target.pathname+target.search+target.hash;
 if(a.closest('.maxx-site-header')&&target.pathname===current.pathname)a.setAttribute('aria-current','page');
}}
update();window.addEventListener('maxbyte:purchase',e=>window.maxByteRememberMission(e.detail.mission_id));
})();
