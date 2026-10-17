(function(){'use strict';
function layout(){
 const shell=document.querySelector('main .dashboard-container'), classic=document.getElementById('gmu-campus-map'), delivery=document.getElementById('robot-control-panel'), game=document.getElementById('snack-chase-panel');
 if(!shell||!classic||!delivery||!game)return false;
 let left=document.getElementById('mb-repaired-map-column'),right=document.getElementById('mb-repaired-controls');
 if(!left){left=document.createElement('section');left.id='mb-repaired-map-column';left.setAttribute('aria-label','Campus map');shell.appendChild(left);}
 if(!right){right=document.createElement('section');right.id='mb-repaired-controls';right.setAttribute('aria-label','Experience controls');shell.appendChild(right);}
 const card=classic.closest('.data-card');
 if(card && card!==left && card!==shell){if(card.parentElement!==left)left.appendChild(card);}
 else if(classic.parentElement!==left)left.appendChild(classic);
 for(const id of ['mb-customize-map','mb-game-map']){const node=document.getElementById(id);if(node&&node.parentElement!==left)left.appendChild(node);}
 const status=document.getElementById('gmu-map-status');if(status&&!card&&status.parentElement!==left)left.appendChild(status);
 if(delivery.parentElement!==right)right.appendChild(delivery);
 if(game.parentElement!==right)right.appendChild(game);
 shell.classList.add('mb-final-layout');window.dispatchEvent(new Event('resize'));return true;
}
let tries=0;function run(){if(!layout()&&++tries<40)setTimeout(run,150)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();
