/* V27: presentation only. Coordinates, routes, game rules and frame sizes stay
   with their existing owners. Shared artwork keeps every delivery bot identical. */
(function(){'use strict';
let hat='none',theme='standard';
try{hat=localStorage.getItem('mb-hat')||hat;theme=localStorage.getItem('mb-map-theme')||theme;}catch(_){}
const hats={none:'',chef:'👨‍🍳',crown:'👑',party:'🎉',cap:'🧢',tophat:'🎩',cowboy:'🤠',graduation:'🎓',helmet:'⛑️',ribbon:'🎀',flower:'🌻',alien:'👽',wizard:'🧙',pumpkin:'🎃',unicorn:'🦄',rocket:'🚀',star:'⭐',rainbow:'🌈',santa:'🎅',butterfly:'🦋',headphones:'🎧',sunglasses:'🕶️',gem:'💎',ball:'⚽'};
if(!(hat in hats))hat='none';
const themes=['standard','soft','night','electric','pulse','water','jungle','lava','ice','sunset','retro','candy'];if(!themes.includes(theme))theme='standard';
window.maxByteRobotIcon=function(color,size,label){
  // Validate dynamic values before using them in inline SVG/HTML.
  color=/^#[0-9a-f]{6}$/i.test(color)?color:'#a855f7';
  size=size===30?30:44;
  label=label==='Player robot'?'Player robot':'Delivery robot';
  return L.divIcon({className:'mb-unified-robot',iconSize:[size,size],iconAnchor:[size/2,size/2],html:
    `<div class="mb-cute-shell" style="width:${size}px;height:${size}px"><svg width="${size}" height="${size}" viewBox="0 0 64 64" role="img" aria-label="${label}"><path d="M32 15V8" stroke="${color}" stroke-width="3"/><circle cx="32" cy="6" r="3" fill="#67e8f9"/><rect x="4" y="24" width="8" height="15" rx="4" fill="${color}"/><rect x="52" y="24" width="8" height="15" rx="4" fill="${color}"/><rect x="10" y="15" width="44" height="31" rx="13" fill="${color}" stroke="white" stroke-width="3"/><rect x="16" y="23" width="32" height="16" rx="8" fill="#172033"/><ellipse cx="24" cy="30" rx="3" ry="4" fill="#67e8f9"/><ellipse cx="40" cy="30" rx="3" ry="4" fill="#67e8f9"/><path d="M28 35Q32 39 36 35" fill="none" stroke="#fff" stroke-width="2"/><circle cx="16" cy="37" r="3" fill="#f9a8d4"/><circle cx="48" cy="37" r="3" fill="#f9a8d4"/><rect x="23" y="45" width="18" height="8" rx="4" fill="${color}"/><circle cx="32" cy="55" r="7" fill="#172033" stroke="white" stroke-width="2"/></svg><span class="mb-big-hat" aria-hidden="true">${hats[hat]}</span></div>`});
};
const style=document.createElement('style');style.textContent=`
/* Game-only legend has no reserved space on the other views. */
body:not(.mb-mode-3) #mb-route-key{display:none!important}
.mb-cute-shell{position:relative;overflow:visible!important}
.mb-cute-shell svg{display:block!important;width:100%!important;height:100%!important}
.mb-big-hat{position:absolute;left:50%;top:-20px;transform:translateX(-50%);font-size:32px;line-height:1;pointer-events:none;filter:drop-shadow(0 1px 1px #fff)}
.mb-unified-robot{background:none!important;border:0!important;overflow:visible!important}
#mb-personality-options{display:flex;flex-wrap:wrap;gap:3px 8px;margin:2px 0}
#mb-personality-options label{display:inline-flex;align-items:center;gap:4px;font-size:12px}
body.mb-mode-1 #mb-personality-options{display:none!important}
.mb-theme-soft .leaflet-tile-pane{filter:saturate(.55) brightness(1.07)}
.mb-theme-night .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.72) saturate(.65)}
.mb-theme-electric .leaflet-tile-pane{filter:contrast(1.4) saturate(2) hue-rotate(160deg)}
.mb-theme-pulse .leaflet-tile-pane{animation:mb-pulse 4s ease-in-out infinite}
.mb-theme-water .leaflet-tile-pane{filter:hue-rotate(145deg) saturate(1.4)}
.mb-theme-jungle .leaflet-tile-pane{filter:hue-rotate(40deg) saturate(1.9)}
.mb-theme-lava .leaflet-tile-pane{filter:sepia(.6) saturate(2.8) hue-rotate(320deg)}
.mb-theme-ice .leaflet-tile-pane{filter:saturate(.5) hue-rotate(150deg) brightness(1.1)}
.mb-theme-sunset .leaflet-tile-pane{filter:sepia(.4) saturate(1.8) hue-rotate(315deg)}
.mb-theme-retro .leaflet-tile-pane{filter:sepia(.8) contrast(1.15)}
.mb-theme-candy .leaflet-tile-pane{filter:hue-rotate(260deg) saturate(1.9)}
@keyframes mb-pulse{50%{filter:saturate(2) hue-rotate(35deg)}}
@media(prefers-reduced-motion:reduce){.mb-theme-pulse .leaflet-tile-pane{animation:none;filter:saturate(1.5)}}
#mb-reward-box{border:2px solid #15803d!important;background:#ecfdf5!important;color:#14532d!important;border-radius:8px;padding:4px 6px!important;box-sizing:border-box;grid-column:1/-1;font-size:11px}
#mb-reward-box p{color:#14532d!important;margin:2px 0!important;font-size:11px!important;line-height:1.15!important}
body:not(.mb-mode-3) #mb-reward-box{display:none!important}
body:not(.mb-mode-3) #sc-message,body:not(.mb-mode-3) #snack-chase-panel > .mb-mission-note{display:none!important}
.mb-game-invitation{border:2px solid #15803d;background:#ecfdf5;color:#14532d;border-radius:8px;padding:5px 7px;margin:5px 0;font-size:11px;line-height:1.2;display:flex;gap:6px;align-items:center;justify-content:space-between}
.mb-game-invitation button{flex-shrink:0;background:#166534;color:white}
.mb-game-invitation[hidden]{display:none!important}
#mb-reward-box p{display:block!important}
#mb-personality-options input[type=color]{flex:none}
@media(max-width:500px){.mb-game-invitation{flex-wrap:wrap}}


`;document.head.append(style);
function redraw(){for(const map of Object.values(window.maxByteMaps||{})){
  for(const t of themes)map.getContainer().classList.toggle('mb-theme-'+t,t===theme);
  map.eachLayer(layer=>{const icon=layer.options?.icon;
    if(icon?.options?.className!=='mb-unified-robot')return;
    const player=icon.options.iconSize[0]===30;
    const color=document.getElementById('sc-color')?.value||'#a855f7';
    layer.setIcon(maxByteRobotIcon(player?'#f97316':color,player?30:44,player?'Player robot':'Delivery robot'));
  });
}}
function ready(){const options=document.getElementById('sc-custom-options');if(!options)return false;
  // Keep the existing color control available in both editable modes.
  options.hidden=(window.maxByteMode||1)===1;options.style.setProperty('display',options.hidden?'none':'flex','important');
  if(!document.getElementById('mb-personality-options')){
    const row=document.createElement('div');row.id='mb-personality-options';
    row.innerHTML='<label>Robot hat <select aria-label="Robot hat"><option value="none">None</option><option value="chef">Chef</option><option value="crown">Crown</option><option value="party">Party</option><option value="cap">Cap</option></select></label><label>Map style <select aria-label="Map style"><option value="standard">Standard</option><option value="soft">Soft</option><option value="night">Night</option></select></label>';
    const [hatSelect,themeSelect]=row.querySelectorAll('select');
    hatSelect.replaceChildren(...Object.keys(hats).map(k=>new Option(k==='none'?'None':hats[k]+' '+k,k)));
    themeSelect.replaceChildren(...themes.map(k=>new Option(k[0].toUpperCase()+k.slice(1),k)));
    hatSelect.value=hat;themeSelect.value=theme;
    function change(){hat=hatSelect.value;theme=themeSelect.value;try{localStorage.setItem('mb-hat',hat);localStorage.setItem('mb-map-theme',theme);}catch(_){}redraw();window.maxByteLayoutRefresh?.();}
    hatSelect.onchange=themeSelect.onchange=change;options.append(row);
  }
  const colorSelect=document.getElementById('sc-color');
  if(colorSelect&&!colorSelect.dataset.rgbRestored){colorSelect.dataset.rgbRestored='true';try{const saved=localStorage.getItem('sc-color');if(/^#[0-9a-f]{6}$/i.test(saved||'')){if(!Array.from(colorSelect.options).some(o=>o.value===saved))colorSelect.add(new Option('Custom',saved));colorSelect.value=saved;colorSelect.dispatchEvent(new Event('change'));}}catch(_){}
  }

  if(colorSelect&&!document.getElementById('mb-any-color')){
    // Native color picker offers the full RGB range, keeping the compact row.
    const label=document.createElement('label');label.textContent='Any color ';
    const picker=document.createElement('input');picker.id='mb-any-color';picker.type='color';picker.value=colorSelect.value;picker.style.cssText='width:32px;height:26px;padding:0';
    picker.oninput=()=>{let o=Array.from(colorSelect.options).find(o=>o.value===picker.value);if(!o){o=new Option('Custom',picker.value);colorSelect.add(o);}colorSelect.value=picker.value;colorSelect.dispatchEvent(new Event('change'));redraw();};
    label.append(picker);options.append(label);
  }
  const arcade=document.getElementById('mb-arcade-controls');
  if(arcade&&!document.getElementById('mb-reward-box')){
    const invite=Array.from(arcade.querySelectorAll('p')).find(p=>p.textContent.includes('PLAY THE SNACK'));
    if(invite){const box=document.createElement('section');box.id='mb-reward-box';
      invite.style.removeProperty('display');invite.prepend('💵 ');box.append(invite);
      const message=document.getElementById('sc-message'),note=document.querySelector('#snack-chase-panel > .mb-mission-note');
      if(message)box.append(message);if(note)box.append(note);arcade.append(box);
    }
  }
  const mode=window.maxByteMode||1;
  const key=document.getElementById('mb-route-key');if(key){key.hidden=mode!==3;key.style.setProperty('display',mode===3?'block':'none','important');}
  const common=document.getElementById('mb-common-telemetry');
  if(common&&!document.getElementById('mb-game-invitation')){
    const invite=document.createElement('aside');invite.id='mb-game-invitation';invite.className='mb-game-invitation';
    const text=document.createElement('span');text.textContent='💵 Play Snack Chase: collect every food piece before delivery arrives to win 15% off your next order.';
    const button=document.createElement('button');button.type='button';button.textContent='Go to Snack Chase';button.onclick=()=>window.maxByteApplyMode?.(3);invite.append(text,button);common.append(invite);
  }
  const promo=document.getElementById('mb-game-invitation');if(promo)promo.hidden=mode===3;
  if(arcade){arcade.hidden=mode!==3;}
  if(mode!==3){const box=document.getElementById('mb-reward-box');if(box)box.hidden=true;}else{const box=document.getElementById('mb-reward-box');if(box)box.hidden=false;}
  redraw();return Boolean(document.getElementById('mb-common-telemetry')&&document.getElementById('mb-reward-box'));
}
for(const name of ['maxbyte:mode','maxbyte:mission','maxbyte:arena','maxbyte:layers'])window.addEventListener(name,()=>{ready();});
const timer=setInterval(()=>{if(ready())clearInterval(timer);},100);
})();
