/* V34: visible checkout state, server-priced totals and one idempotent purchase.
   The browser never supplies paid status or decides coupon eligibility. */
(async()=>{'use strict';const $=id=>document.getElementById(id),form=$('orderForm');if(!form)return;
const params=new URLSearchParams(location.search);let csrf='',busy=false,completed=false,demo=false;
function newKey(){const b=new Uint8Array(16);crypto.getRandomValues(b);b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
let key=newKey();function money(n){return '$'+(n/100).toFixed(2);}function message(text,error=false){$('purchase-status').textContent=text;$('purchase-status').dataset.error=String(error);}
async function api(path,options={}){const r=await fetch('/api/customer/'+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});let d;try{d=await r.json();}catch(_){throw Error('The website API is unavailable. Please try again shortly.');}if(!r.ok)throw Error(d.error||'Checkout could not be completed.');return d;}
function body(){return {mission_id:$('purchase-mission').value,items:[{sku:$('food').value,quantity:Number($('purchase-quantity').value)}],coupon_code:$('purchase-coupon').value.trim()};}
function totals(d){$('summaryMeal').textContent=d.items.map(x=>x.name+' × '+x.quantity).join(', ');for(const [id,name] of [['summarySubtotal','subtotal_cents'],['summaryDiscount','discount_cents'],['summaryDelivery','delivery_cents'],['summaryTotal','total_cents']])$(id).textContent=(name==='discount_cents'?'−':'')+money(d[name]);}
async function quote(){if(!form.reportValidity()){message('Choose a saved location, meal and valid quantity.',true);return false;}try{totals(await api('checkout/quote',{method:'POST',body:JSON.stringify(body())}));message(demo?'Demo total updated. No money will be charged.':'Total updated. Online payment is not connected yet.');return true;}catch(e){message(e.message,true);return false;}}
$('purchase-quote').onclick=quote;
for(const id of ['purchase-mission','food','purchase-quantity','purchase-coupon'])$(id).addEventListener('change',()=>{if(completed)return;key=newKey();$('summaryTotal').textContent='Update total';});
// Keep the idempotency key stable across failures, retries and repeated clicks.
form.addEventListener('submit',async event=>{event.preventDefault();if(busy||completed)return;if(!demo){message('Online payment is not connected yet. No purchase was made.',true);return;}if(!form.reportValidity()){message('Choose your location and meal before checkout.',true);return;}
 busy=true;$('purchase-submit').disabled=true;message('Completing your demo purchase…');
 try{const result=await api('checkout/complete',{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(body())});
 const target=new URL(result.map_url,location.href);if(target.origin!==location.origin||!['/MapAPI.html','/tracking.html'].includes(target.pathname))throw Error('Purchase saved, but its map link could not be opened. Check your account before retrying.');
 completed=true;message((result.notice||'Demo purchase completed.')+' Your delivery maps and game are ready.');$('purchase-open-map').href=target.pathname+target.search;$('purchase-result').hidden=false;$('purchase-submit').textContent='Demo purchase completed';
 for(const id of ['purchase-mission','food','purchase-quantity','purchase-coupon'])$(id).disabled=true;
 const mission=target.searchParams.get('mission');if(mission)window.dispatchEvent(new CustomEvent('maxbyte:purchase',{detail:{mission_id:mission}}));
 $('purchase-open-map').focus({preventScroll:true});
 }catch(e){message(e.message,true);}finally{busy=false;$('purchase-submit').disabled=completed||!demo;}
});
try{const session=await api('session');csrf=session.csrf_token;const catalogue=await api('checkout/catalogue');demo=catalogue.demo_checkout===true;
 $('food').replaceChildren(new Option('Choose a meal',''),...catalogue.items.map(x=>new Option(x.name+' — '+money(x.price_cents),x.sku)));
 $('checkout-mode').textContent=demo?'LOCAL DEMO · No payment is taken and no food is dispatched.':'Online payments are not connected yet. You can preview totals; purchase completion is unavailable.';
 $('purchase-submit').textContent=demo?'Complete demo checkout — no charge':'Checkout unavailable';
 if(!session.authenticated){$('purchase-mission').replaceChildren(new Option('Sign in to choose a saved location',''));message('Sign in or create an account, then choose your saved delivery location.',true);return;}
 const saved=await api('missions');$('purchase-mission').replaceChildren(new Option('Choose a saved delivery location',''),...saved.missions.map(m=>new Option(m.destination_name+(m.reference?' · '+m.reference:''),m.mission_id)));
 const wanted=params.get('mission');if(saved.missions.some(m=>m.mission_id===wanted))$('purchase-mission').value=wanted;else if(saved.missions.length===1)$('purchase-mission').value=saved.missions[0].mission_id;
 $('purchase-coupon').value=params.get('coupon')||'';$('purchase-submit').disabled=!demo||!saved.missions.length;
 message(!saved.missions.length?'Save a delivery location first.':demo?'Choose a meal, then complete demo checkout. No money is charged.':'Choose a meal to preview your total. Payment connection is pending.');
}catch(e){message(e.message,true);$('purchase-submit').disabled=true;}
})();
