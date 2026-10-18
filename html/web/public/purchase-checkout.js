/* V35: account -> server-priced order -> simulated wallet -> confirmed purchase.
   No card details, payment provider, actual charge or physical robot command. */
(async()=>{'use strict';const $=id=>document.getElementById(id),form=$('orderForm');if(!form)return;
const params=new URLSearchParams(location.search),dialog=$('demo-payment-dialog');let csrf='',busy=false,completed=false,demo=false,intent=null;
function newKey(){const b=new Uint8Array(16);crypto.getRandomValues(b);b[6]=(b[6]&15)|64;b[8]=(b[8]&63)|128;const h=Array.from(b,x=>x.toString(16).padStart(2,'0')).join('');return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;}
let key=newKey();function money(n){return '$'+(n/100).toFixed(2);}function message(text,error=false){$('purchase-status').textContent=text;$('purchase-status').dataset.error=String(error);}
const fields=['purchase-mission','food','purchase-quantity','purchase-coupon'];function lock(value){for(const id of fields)$(id).disabled=value;$('purchase-quote').disabled=value;}
async function api(path,options={}){const r=await fetch('/api/customer/'+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});let d;try{d=await r.json();}catch(_){throw Error('The demonstration API is unavailable. Please try again shortly.');}if(!r.ok)throw Error(d.error||'Your order could not be completed.');return d;}
function body(){return {mission_id:$('purchase-mission').value,items:[{sku:$('food').value,quantity:Number($('purchase-quantity').value)}],coupon_code:$('purchase-coupon').value.trim()};}
function totals(d){$('summaryMeal').textContent=d.items.map(x=>x.name+' × '+x.quantity).join(', ');for(const [id,name] of [['summarySubtotal','subtotal_cents'],['summaryDiscount','discount_cents'],['summaryDelivery','delivery_cents'],['summaryTotal','total_cents']])$(id).textContent=(name==='discount_cents'?'−':'')+money(d[name]);}
async function quote(){if(!form.reportValidity()){message('Choose a saved location, meal and valid quantity.',true);return false;}try{totals(await api('checkout/quote',{method:'POST',body:JSON.stringify(body())}));message('Demo total updated. Actual charge: $0.00.');return true;}catch(e){message(e.message,true);return false;}}
$('purchase-quote').onclick=quote;for(const id of fields)$(id).addEventListener('change',()=>{if(completed)return;key=newKey();intent=null;$('summaryTotal').textContent='Update total';});
function cancelPayment(){if(busy||completed)return;dialog.close();intent=null;key=newKey();lock(false);$('purchase-submit').disabled=!demo;message('Payment not completed. Your delivery has not started.');}
$('demo-payment-cancel').onclick=cancelPayment;dialog.addEventListener('cancel',event=>{event.preventDefault();cancelPayment();});
form.addEventListener('submit',async event=>{event.preventDefault();if(busy||completed||dialog.open)return;if(!demo){message('Demonstration checkout is disabled.',true);return;}if(!form.reportValidity()){message('Choose your location and meal before continuing.',true);return;}
 busy=true;$('purchase-submit').disabled=true;const cart=body();lock(true);message('Preparing your simulated payment…');
 try{const priced=await api('checkout/quote',{method:'POST',body:JSON.stringify(cart)});totals(priced);
 intent=await api('checkout/demo-payment',{method:'POST',headers:{'Idempotency-Key':key},body:JSON.stringify(cart)});$('demo-payment-total').textContent=money(intent.total_cents);$('demo-payment-status').textContent='Review your order, then confirm the simulated payment. No money will be charged.';dialog.showModal();message('Awaiting simulated payment confirmation. Delivery has not started.');
 }catch(e){message(e.message,true);lock(false);$('purchase-submit').disabled=!demo;}finally{busy=false;}
});
$('demo-payment-confirm').onclick=async()=>{if(busy||completed||!intent)return;busy=true;$('demo-payment-confirm').disabled=$('demo-payment-cancel').disabled=true;$('demo-payment-status').textContent='Confirming simulated payment…';
 try{const result=await api('checkout/demo-payment/'+encodeURIComponent(intent.payment_id)+'/confirm',{method:'POST',body:'{}'});
 if(result.payment_status!=='succeeded_simulated'||result.charged_cents!==0)throw Error('Unexpected demonstration payment response.');
 const target=new URL(result.map_url,location.href);if(target.origin!==location.origin||target.pathname!=='/MapAPI.html')throw Error('Your order was saved, but its Classic Map link is unavailable.');
 completed=true;totals(result);dialog.close();message('Payment successful (simulated). No money charged. Opening Classic Map with your delivery running…');$('purchase-open-map').href=target.pathname+target.search;$('purchase-open-map').textContent='Open Classic Map — delivery started';$('purchase-result').hidden=false;$('purchase-submit').textContent='Simulated payment successful';
 const mission=target.searchParams.get('mission');window.dispatchEvent(new CustomEvent('maxbyte:purchase',{detail:{mission_id:mission}}));setTimeout(()=>location.assign(target.pathname+target.search),800);
 }catch(e){$('demo-payment-status').textContent=e.message;message(e.message,true);}finally{busy=false;$('demo-payment-confirm').disabled=$('demo-payment-cancel').disabled=false;}
};
try{const session=await api('session');csrf=session.csrf_token;const catalogue=await api('checkout/catalogue');demo=catalogue.demo_checkout===true;
 $('food').replaceChildren(new Option('Choose a meal',''),...catalogue.items.map(x=>new Option(x.name+' — '+money(x.price_cents),x.sku)));
 $('checkout-mode').textContent='DEMONSTRATION · Simulated payment, $0.00 charged. The robot journey is a simulation; no real food is dispatched.';$('purchase-submit').textContent=demo?'Continue to simulated payment':'Demonstration checkout unavailable';
 if(!session.authenticated){lock(true);message('Create an account or sign in before placing your order.',true);const login=Array.from(form.querySelectorAll('a')).find(a=>new URL(a.href).pathname==='/login.html');if(login)login.href='login.html?next='+encodeURIComponent('order.html'+location.search);return;}
 const saved=await api('missions');$('purchase-mission').replaceChildren(new Option('Choose a saved delivery location',''),...saved.missions.map(m=>new Option(m.destination_name+(m.reference?' · '+m.reference:''),m.mission_id)));
 const wanted=params.get('mission');if(saved.missions.some(m=>m.mission_id===wanted))$('purchase-mission').value=wanted;else if(saved.missions.length===1)$('purchase-mission').value=saved.missions[0].mission_id;
 $('purchase-coupon').value=params.get('coupon')||'';$('purchase-submit').disabled=!demo||!saved.missions.length;message(!saved.missions.length?'Save a delivery location before placing your order.':demo?'Choose your meal, then review and confirm the simulated payment.':'Demonstration checkout is disabled.');
}catch(e){message(e.message,true);$('purchase-submit').disabled=true;}
})();
