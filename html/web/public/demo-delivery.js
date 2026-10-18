/* V35: only an account-owned confirmed purchase can start an automatic journey.
   This follows a server clock and never sends commands to physical hardware. */
(()=>{'use strict';const mission=new URLSearchParams(location.search).get('mission');if(!mission)return;let loading=false,attached=false,attempts=0,first=true;
async function attach(){if(attached||loading||!window.maxByteMissionControl||!window.maxByteRoutePlan)return;loading=true;
try{const response=await fetch('/api/customer/missions/'+encodeURIComponent(mission)+'/delivery',{credentials:'same-origin',cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'Complete checkout before starting delivery.');
 if(data.mission_id!==mission||data.simulated!==true||data.payment_status!=='succeeded_simulated')throw Error('Purchase confirmation is unavailable.');
 window.maxBytePurchaseDelivery=data;if(first){window.maxByteApplyMode?.(1);first=false;}window.maxByteMissionControl.startPurchase(data);attached=true;
 const title=document.querySelector('#mb-common-telemetry h3');if(title)title.textContent='Simulated delivery and return';
 for(const button of document.querySelectorAll('#snack-chase-panel [data-action]'))button.disabled=true;
 window.dispatchEvent(new CustomEvent('maxbyte:dispatch',{detail:data}));
}catch(error){const status=document.getElementById('robot-simulation-status');if(status){status.textContent=error.message+' ';const link=document.createElement('a');link.href='order.html?mission='+encodeURIComponent(mission);link.textContent='Complete your order';status.append(link);}attached=true;
 for(const id of ['robot-start','robot-pause','robot-reset']){const e=document.getElementById(id);if(e)e.disabled=true;}
}finally{loading=false;}}
window.addEventListener('maxbyte:mission',attach);window.addEventListener('pageshow',()=>{attached=false;attach();});document.addEventListener('visibilitychange',()=>{if(!document.hidden){attached=false;attach();}});const timer=setInterval(()=>{attach();if(attached||++attempts>=150)clearInterval(timer);},100);
})();
