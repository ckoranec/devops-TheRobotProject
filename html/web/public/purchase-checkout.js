/* V31 checkout: server catalogue, account destinations and atomic coupon use.
   Demo mode is explicit; no customer identity or form values go into a URL. */
(async()=>{'use strict';
// V33: secure request keys also work when randomUUID is unavailable on HTTP.
function newRequestKey(){
 const bytes=new Uint8Array(16);globalThis.crypto.getRandomValues(bytes);
 bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const h=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
 return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);
}
const form=document.getElementById('orderForm');if(!form)return;
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search);let csrf='',key=newRequestKey(),busy=false;
const panel=document.createElement('section');panel.innerHTML='<p id="purchase-status" role="status">Loading account checkout…</p><label>Saved delivery location <select id="purchase-mission" required></select></label><p><a href="delivery-location.html">Sign in / save a delivery location</a> · <a href="coupon-wallet.html">Coupon wallet</a></p><label>Quantity <input id="purchase-quantity" type="number" min="1" max="20" value="1" required></label><label>Coupon code <input id="purchase-coupon" maxlength="40" autocomplete="off"></label><button type="button" id="purchase-quote">Update total</button>';
form.prepend(panel);form.removeAttribute('action');form.removeAttribute('method');
for(const id of ['name','studentId'])if($(id))$(id).required=false;
const status=$('purchase-status'),submit=form.querySelector('[type=submit]');submit.disabled=true;
function message(text){status.textContent=text;}
function money(cents){return '$'+(cents/100).toFixed(2);}
async function api(path,options={}){const r=await fetch('/api/customer/'+path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});let d;try{d=await r.json();}catch(_){throw Error('Website/API unavailable. Keep the port 8000 preview running.');}if(!r.ok)throw Error(d.error||'Checkout request failed');return d;}
function body(){return {mission_id:$('purchase-mission').value,items:[{sku:$('food').value,quantity:Number($('purchase-quantity').value)}],coupon_code:$('purchase-coupon').value.trim()};}
async function quote(){if(!body().mission_id||!body().items[0].sku){message('Choose a saved delivery location and meal.');return false;}try{const totals=await api('checkout/quote',{method:'POST',body:JSON.stringify(body())});$('summaryMeal').textContent=totals.items[0].name+' × '+totals.items[0].quantity;$('summaryTotal').textContent=money(totals.total_cents);message((totals.demo_checkout?'LOCAL DEMONSTRATION — no money will be charged. ':'')+'Food '+money(totals.subtotal_cents)+' · Coupon −'+money(totals.discount_cents)+' · Delivery '+money(totals.delivery_cents));return true;}catch(e){message(e.message);return false;}}
$('purchase-quote').onclick=quote;
for(const id of ['purchase-mission','purchase-quantity','purchase-coupon'])$(id).addEventListener('input',()=>{key=newRequestKey();$('summaryTotal').textContent='Update total';});
$('food').onchange=()=>{key=newRequestKey();quote();};
form.onsubmit=async event=>{event.preventDefault();if(busy||!form.reportValidity())return;busy=true;submit.disabled=true;try{const r=await api('checkout/complete',{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(body())});message((r.notice||'Purchase recorded.')+' Purchase '+r.purchase_id);let link=$('purchase-open-map');if(!link){link=document.createElement('a');link.id='purchase-open-map';panel.append(link);}link.textContent='Open this purchase’s delivery maps and one Snack Chase game';link.href=r.map_url;await quote();}catch(e){message(e.message);}finally{busy=false;submit.disabled=false;}};
try{const session=await api('session');csrf=session.csrf_token;const catalogue=await api('checkout/catalogue');$('food').replaceChildren(new Option('-- Choose a meal --',''),...catalogue.items.map(item=>new Option(item.name+' — '+money(item.price_cents),item.sku)));
if(!session.authenticated){message('Sign in using Delivery Location, then return to checkout.');return;}
const saved=await api('missions');$('purchase-mission').replaceChildren(...saved.missions.map(m=>new Option(m.destination_name+' · '+(m.reference||m.mission_id),m.mission_id)));
if(params.has('mission')&&saved.missions.some(m=>m.mission_id===params.get('mission')))$('purchase-mission').value=params.get('mission');
$('purchase-coupon').value=params.get('coupon')||'';
submit.disabled=!saved.missions.length;submit.textContent=catalogue.demo_checkout?'Complete demo checkout — no charge':'Complete checkout';message(catalogue.demo_checkout?'LOCAL DEMONSTRATION — no money charged and no food dispatched. Each demo purchase grants one game attempt.':'Payment connection is not available yet. Quotes work; purchases remain disabled.');if(!catalogue.demo_checkout)submit.disabled=true;
}catch(e){message(e.message);}
})();
