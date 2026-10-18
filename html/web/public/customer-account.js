/* Real same-origin account endpoints; no simulated login, 2FA or recovery success. */
(async()=>{'use strict';const $=id=>document.getElementById(id);let busy=false,csrf='';
function message(text){$('account-status').textContent=text;}
const next=new URL(new URLSearchParams(location.search).get('next')||'delivery-location.html',location.href);
const allowed=['/delivery-location.html','/order.html','/coupon-wallet.html','/tracking.html','/MapAPI.html'];
if(next.origin!==location.origin||!allowed.includes(next.pathname))next.href=new URL('delivery-location.html',location.href).href;
const mission=new URLSearchParams(location.search).get('mission');if(mission&&/^[0-9a-f-]{36}$/i.test(mission))next.searchParams.set('mission',mission);
$('account-continue').href=next.pathname+next.search+next.hash;
async function api(path,options={}){const r=await fetch('/api/'+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}});let d;try{d=await r.json();}catch(_){throw Error('Your account service is unavailable. Please try again shortly.');}if(!r.ok)throw Error(d.error||'Sign-in failed.');return d;}
async function session(){const s=await api('customer/session');csrf=s.csrf_token;$('account-signout').hidden=!s.authenticated;$('account-continue').hidden=!s.authenticated;message(s.authenticated?'Signed in as '+s.email:'Sign in or create your account to continue.');}
async function authenticate(create){if(busy||!$('customer-account-form').reportValidity())return;busy=true;$('account-signin').disabled=$('account-create').disabled=true;
try{const credentials={email:$('email').value.trim(),password:$('password').value};if(create)await api('auth/register',{method:'POST',body:JSON.stringify(credentials)});await api('auth/login',{method:'POST',body:JSON.stringify(credentials)});$('password').value='';await session();location.assign(next.pathname+next.search+next.hash);}catch(e){message(e.message);}finally{busy=false;$('account-signin').disabled=$('account-create').disabled=false;}}
$('customer-account-form').onsubmit=e=>{e.preventDefault();authenticate(false);};$('account-create').onclick=()=>authenticate(true);
$('account-signout').onclick=async()=>{try{await api('auth/logout',{method:'POST',body:'{}'});await session();}catch(e){message(e.message);}};
try{await session();}catch(e){message(e.message);}
})();
