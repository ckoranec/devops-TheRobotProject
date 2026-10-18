/* V22: one telemetry panel and a viewport-sized desktop frame.
   Mobile and unusually short windows use normal page flow, never clipped content. */
(function(){'use strict';const $=id=>document.getElementById(id);let frame=null;
function set(e,p){if(e)for(const [k,v] of Object.entries(p))e.style.setProperty(k,String(v),'important');}
const timer=setInterval(()=>{const shell=document.querySelector('.dashboard-container'),maps=[$('gmu-campus-map'),$('mb-customize-map'),$('mb-game-map')],robot=$('robot-control-panel'),snack=$('snack-chase-panel'),layers=$('mb-gis-controls'),modes=$('max-byte-modes'),status=$('robot-simulation-status');if(!shell||maps.some(m=>!m)||!robot||!snack||!layers||!modes||!status)return;clearInterval(timer);
const card=maps[0].closest('.data-card'),left=document.createElement('section'),right=document.createElement('section'),stack=document.createElement('section');left.id='mb-repaired-map-column';right.id='mb-repaired-controls';stack.id='mb-mission-control-stack';shell.append(left,right);left.append(card);right.append(stack,layers);card.append(maps[1],maps[2]);const source=$('gmu-map-status');if(source)card.append(source);
// Move the actual simulator's status and controls, preserving its handlers.
const common=document.createElement('section');common.id='mb-common-telemetry';common.innerHTML='<h3>Delivery and return</h3>';const actions=robot.querySelector('.mb-mission-buttons'),speed=$('robot-preview-speed'),note=robot.querySelector('.mb-mission-note');common.append(actions,status,note);if(speed){speed.innerHTML='<option value="15" selected>15 mph</option>';speed.value='15';speed.dispatchEvent(new Event('change'));}
stack.append(common,snack);robot.hidden=true;set(robot,{display:'none'});const extra=snack.querySelector('.mb-mission-buttons');if(extra){extra.hidden=true;set(extra,{display:'none'});}const old=$('mb-shared-delivery-summary');if(old)old.remove();set(snack.querySelector('.mb-mission-note'),{'font-size':'10px'});
set(document.body,{'overflow-y':'auto',height:'auto','max-height':'none'});const main=shell.closest('main');set(main,{height:'auto','max-height':'none',overflow:'visible',padding:'8px 0 12px'});
const header=document.querySelector('body > header');set(header,{display:'flex','flex-wrap':'wrap','align-items':'center','justify-content':'center',gap:'8px 24px',padding:'8px 12px',height:'auto'});set(header?.querySelector('h1'),{margin:'0','font-size':'23px'});header?.querySelectorAll('nav,ul').forEach(e=>set(e,{margin:'0',padding:'0'}));header?.querySelectorAll('li,a').forEach(e=>set(e,{'font-size':'14px',padding:'4px'}));
set(shell,{display:'grid','grid-template-rows':'auto auto',gap:'8px',padding:'0',margin:'0 auto',width:'94vw','max-width':'1400px','align-items':'stretch'});set(modes,{'grid-column':'1 / -1','grid-row':'1',display:'flex','flex-wrap':'wrap','align-items':'center',gap:'4px 10px',padding:'8px 12px',margin:'0'});modes.querySelectorAll('p').forEach(e=>set(e,{margin:'0','font-size':'11px','line-height':'1.2','flex-basis':'100%'}));modes.querySelectorAll('button').forEach(e=>set(e,{'min-height':'32px',padding:'4px 9px',margin:'0','font-size':'13px'}));
set(left,{'grid-column':'1','grid-row':'2',padding:'8px',margin:'0','min-width':'0','box-sizing':'border-box'});set(card,{display:'grid','grid-template-columns':'minmax(0,1fr)','grid-template-rows':'auto auto minmax(0,1fr) auto',gap:'4px',height:'100%',padding:'0',margin:'0','min-height':'0'});for(const e of card.children)if(e.matches('h3,p'))set(e,{margin:'0','font-size':e.tagName==='H3'?'16px':'11px','line-height':'1.2'});if(source)set(source,{'grid-column':'1','grid-row':'4'});for(const m of maps)set(m,{'grid-column':'1','grid-row':'3',width:'100%',height:'100%','min-height':'0','max-height':'none',margin:'0'});
set(right,{display:'grid','grid-template-columns':'minmax(0,1fr)','grid-template-rows':'1fr 1fr',gap:'0',padding:'0',margin:'0','min-width':'0'});set(stack,{padding:'10px',margin:'0','box-sizing':'border-box',background:'rgba(249,241,252,.98)',color:'#31114b','border-radius':'14px 14px 0 0',overflow:'visible'});set(layers,{padding:'10px',margin:'0',width:'100%','box-sizing':'border-box',background:'#171d36',color:'#fff','border-radius':'0 0 14px 14px',overflow:'visible',position:'static','min-height':'0','max-height':'none'});
set(snack,{padding:'0',margin:'0',width:'100%',height:'auto','max-height':'none',overflow:'visible',background:'transparent',border:'0','box-shadow':'none',position:'static'});set(status,{display:'block',margin:'4px 0'});
for(const panel of [common,snack]){panel.querySelectorAll('h3').forEach(e=>set(e,{margin:'0 0 4px','font-size':'15px',color:'#31114b'}));panel.querySelectorAll('p,label').forEach(e=>set(e,{margin:'3px 0','font-size':'12px','line-height':'1.25',color:'#31114b'}));panel.querySelectorAll('button,select').forEach(e=>set(e,{'min-height':'29px','min-width':'32px',padding:'3px 7px',margin:'1px','font-size':'12px'}));}set(note,{'font-size':'10px'});set(snack.querySelector('h3'),{display:'none'});set(actions,{display:'flex','flex-wrap':'wrap',gap:'3px'});
// Compact the game direction pad into a single row; all four buttons remain usable.
set(snack.querySelector('.sc-pad'),{display:'flex','justify-content':'flex-start',gap:'4px',padding:'0',margin:'3px 0'});layers.querySelectorAll('h3,p,label,summary,small').forEach(e=>set(e,{'font-size':e.tagName==='H3'?'15px':'11px','line-height':'1.2',margin:'3px 0',color:'#f1f5f9'}));set(layers.querySelector('[data-toggles]'),{display:'grid','grid-template-columns':'repeat(2,minmax(0,1fr))',gap:'4px'});

const arcade=$('mb-arcade-controls');set(arcade.querySelector('p'),{display:'none'});set(arcade.querySelector('.sc-stats'),{'grid-column':'1 / -1','grid-row':'1','font-size':'12px'});set(arcade.querySelector('.mb-mission-buttons'),{'grid-column':'1','grid-row':'2',display:'flex','flex-wrap':'wrap',gap:'3px'});set(arcade.querySelector('.sc-pad'),{'grid-column':'2','grid-row':'2'});set(arcade.querySelector('p:last-child'),{'grid-column':'1 / -1','grid-row':'3','font-size':'11px'});
function layout(){cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{const mode=window.maxByteMode||1,narrow=innerWidth<900;set(shell,{'grid-template-columns':narrow?'minmax(0,1fr)':'minmax(0,1fr) minmax(0,1fr)'});set(right,{'grid-column':narrow?'1':'2','grid-row':narrow?'3':'2'});maps.forEach((m,i)=>set(m,{display:i+1===mode?'block':'none'}));set(snack,{display:mode===1?'none':'block'});set(arcade,{display:mode===3?'grid':'none','grid-template-columns':'minmax(0,1fr) auto',gap:'2px 6px','align-items':'center'});const title=card.querySelector('h3');if(title)title.textContent='Horizon Hall delivery and return';
// Measure content before sizing. Normal desktop fits below the compact header.

// V25: exclude stretched grid space from the content measurement.
set(right,{
    height:'auto',
    'align-self':'start',
    'grid-template-rows':'max-content max-content'
});
set(stack,{height:'auto','align-self':'start'});
set(layers,{height:'auto','align-self':'start'});

// Keep layer labels and the file control compact.
layers.querySelectorAll('label,label span,p,small,summary').forEach(
    e=>set(e,{
        'font-size':'11px',
        'line-height':'1.2',
        margin:'3px 0'
    })
);
set(layers.querySelector('[data-import]'),{
    'font-size':'11px',
    'min-height':'0',
    height:'30px',
    padding:'2px',
    'max-width':'100%',
    'box-sizing':'border-box'
});
const natural=Math.max(stack.scrollHeight,layers.scrollHeight),available=Math.floor(innerHeight-left.getBoundingClientRect().top-32);const fits=!narrow&&available>=500&&natural<=available/2;const total=fits?available:Math.max(560,2*natural+12);set(left,{height:(narrow?520:total)+'px'});set(right,{height:total+'px','grid-template-rows':'minmax(0,1fr) minmax(0,1fr)'});set(stack,{height:'100%','align-self':'stretch'});set(layers,{height:'100%','align-self':'stretch'});const map=window.maxByteMaps?.[mode];if(map){map.invalidateSize({pan:false});if(window.maxByteCommonBounds)map.fitBounds(window.maxByteCommonBounds(),{padding:[35,35],animate:false});}
});}
for(const event of ['resize','maxbyte:mode','maxbyte:mission','maxbyte:layers','maxbyte:arena'])window.addEventListener(event,layout);layers.addEventListener('toggle',layout,true);window.maxByteLayoutRefresh=layout;layout();
},80);
})();
