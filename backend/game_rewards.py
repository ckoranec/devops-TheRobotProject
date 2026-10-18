"""Server-authoritative promotional game. Never trusts client scores or geometry.
Movement, food collision, deadline, wallet ownership and coupon issuance live here.
V31 binds each game and coupon to one confirmed purchase. Local demo purchases
are explicit; real payment confirmation remains an external integration.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import secrets
import time
import uuid
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from backend.app import db
from backend.customer_routes import CustomerMission, RouteInputError, protect_write, bad_input

class SnackRun(db.Model):
    __tablename__='snack_runs'
    id=db.Column(db.String(36),primary_key=True)
    mission_id=db.Column(db.String(36),db.ForeignKey('customer_route_missions.id'),unique=True,nullable=False)
    owner_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    state=db.Column(db.Text,nullable=False)
    revision=db.Column(db.Integer,nullable=False,default=0)
    __mapper_args__={'version_id_col':revision}

class LegacySnackCoupon(db.Model):
    __tablename__='snack_coupons'
    id=db.Column(db.String(36),primary_key=True)
    owner_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    run_id=db.Column(db.String(36),db.ForeignKey('snack_runs.id'),nullable=False,unique=True)
    reward_day=db.Column(db.Integer,nullable=False)
    __table_args__=(db.UniqueConstraint('owner_id','reward_day',name='uq_snack_daily_reward'),)
    code=db.Column(db.String(40),nullable=False,unique=True)
    issued_at=db.Column(db.Float,nullable=False)
    expires_at=db.Column(db.Float,nullable=False)
    # Redemption is intentionally reserved for an actual server-owned checkout.
    redeemed_order_id=db.Column(db.String(80),nullable=True,unique=True)

# V31: retain V30 records, but purchase rewards use a new table without daily limits.
from backend.purchase_checkout import PurchaseCoupon as SnackCoupon, eligible_purchase, register_checkout

bp=Blueprint('snack_rewards',__name__,url_prefix='/api/customer')
bp.before_request(protect_write)
bp.register_error_handler(RouteInputError,bad_input)
bp.register_error_handler(429,lambda error:(jsonify(error='Too many game requests. Please wait.',code='rate_limited'),429))

def now():return current_app.config.get('SNACK_CLOCK',time.time)()
def fail(code,message,status=400):raise RouteInputError(code,message,status)
def owned(mission_id):
    row=CustomerMission.query.filter_by(id=mission_id,owner_id=current_user.id).first()
    if not row:fail('not_found','Mission not found.',404)
    return row

def arena(mission):
    path=Path(current_app.config.get('SNACK_NETWORK_SOURCE',Path(current_app.root_path).parent/'html/web/public/data/mission-network.json'))
    try:network=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):fail('game_unavailable','Game streets are unavailable.',503)
    if network.get('map_sha256')!=mission['metadata']['map_sha256']:fail('stale_game_map','Game streets and mission use different map versions.',409)
    leg=next(f for f in mission['features'] if f['properties']['leg']=='outbound')
    lon,lat=leg['geometry']['coordinates'][-1]
    def xy(ll):return [(ll[1]-lon)*111195*math.cos(math.radians(lat)),(ll[0]-lat)*111195]
    candidates=[i for i,ll in network['nodes'].items() if math.hypot(*xy(ll))<=450]
    if not candidates:fail('game_coverage','No game streets at this destination.',422)
    selected=set(candidates);adj=network['adj']
    links={i:sorted({str(e['to']) for e in adj.get(i,[]) if str(e['to']) in selected and any(str(x['to'])==i for x in adj.get(str(e['to']),[]))}) for i in candidates}
    start=min(candidates,key=lambda i:math.hypot(*xy(network['nodes'][i])))
    queue=[start];seen={start}
    for i in queue:
        for j in links[i]:
            if j not in seen:seen.add(j);queue.append(j)
    nodes={i:{'ll':network['nodes'][i],'xy':xy(network['nodes'][i]),'links':[j for j in links[i] if j in seen]} for i in sorted(seen)}
    if len(nodes)<20:fail('game_coverage','Not enough connected game streets.',422)
    def distance(a,b):return math.dist(nodes[a]['xy'],nodes[b]['xy'])
    patrol=[start]
    while len(patrol)<min(18,len(nodes)):
        remaining=[i for i in nodes if i not in patrol]
        patrol.append(max(remaining,key=lambda i:min(distance(i,j) for j in patrol)))
    foods=[]
    for _ in range(5):
        remaining=[i for i in nodes if distance(i,start)>=180 and i not in foods and all(distance(i,j)>=100 for j in foods)]
        if not remaining:fail('game_coverage','Not enough space for separated food pieces.',422)
        foods.append(max(remaining,key=lambda i:min([distance(i,start)]+[distance(i,j) for j in foods])))
    return {'nodes':nodes,'start':start,'patrol':patrol,'foodStarts':foods}

def entity(node):return {'node':node,'to':None,'travel':0,'steps':[]}
def position(graph,e):
    a=graph['nodes'][e['node']]
    if not e['to']:return a['ll'],a['xy']
    b=graph['nodes'][e['to']];length=math.dist(a['xy'],b['xy']);t=e['travel']/length if length else 0
    return [a['ll'][k]+(b['ll'][k]-a['ll'][k])*t for k in range(2)],[a['xy'][k]+(b['xy'][k]-a['xy'][k])*t for k in range(2)]
def advance(graph,e,meters,choose):
    for _ in range(200):
        if meters<=0:break
        if not e['to']:
            e['to']=choose(e)
            if not e['to']:break
            e['travel']=0
        a,b=graph['nodes'][e['node']],graph['nodes'][e['to']]
        length=math.dist(a['xy'],b['xy']);step=min(meters,length-e['travel']);e['travel']+=step;meters-=step
        if e['travel']>=length-1e-7:e['node']=e['to'];e['to']=None;e['travel']=0
        else:break

def directional(graph,e,direction):
    vector={'up':(0,1),'down':(0,-1),'left':(-1,0),'right':(1,0)}.get(direction)
    if not vector:return None
    a=graph['nodes'][e['node']]['xy'];best=None;score=.25
    for i in graph['nodes'][e['node']]['links']:
        b=graph['nodes'][i]['xy'];dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length and (value:=(dx*vector[0]+dy*vector[1])/length)>score:score=value;best=i
    return best

def food_next(graph,e):
    if not e['steps']:
        goal=secrets.choice(graph['patrol']);queue=[e['node']];prev={e['node']:None}
        for i in queue:
            if goal in prev:break
            for j in graph['nodes'][i]['links']:
                if j not in prev:prev[j]=i;queue.append(j)
        if goal not in prev:return None
        path=[goal]
        while path[0]!=e['node']:path.insert(0,prev[path[0]])
        e['steps']=path[1:]
    return e['steps'].pop(0) if e['steps'] else None

def swept(a,b,c,d):
    x,y=a[0]-c[0],a[1]-c[1];vx,vy=(b[0]-a[0])-(d[0]-c[0]),(b[1]-a[1])-(d[1]-c[1]);den=vx*vx+vy*vy
    t=max(0,min(1,-(x*vx+y*vy)/den)) if den else 0
    return math.hypot(x+t*vx,y+t*vy)

def coupon_json(c):
    return {'coupon_id':c.id,'code':c.code,'percent_off':15,'expires_at':datetime.fromtimestamp(c.expires_at,timezone.utc).isoformat(),'status':'redeemed' if c.redeemed_order_id else 'expired' if now()>=c.expires_at else 'available','checkout_connected':True,'purchase_id':c.purchase_id}
def snapshot(run,state):
    graph=state['graph'];coupon=SnackCoupon.query.filter_by(run_id=run.id).first()
    return {'run_id':run.id,'state':state['status'],'caught':5-len(state['foods']),'elapsed_seconds':max(0,now()-state['started']),'delivery_eta_seconds':max(0,state['deadline']-now()),'player':position(graph,state['player'])[0],
            'foods':[{'id':f['id'],'position':position(graph,f)[0]} for f in state['foods']],
            'coupon':coupon_json(coupon) if coupon else None,'reward_message':state.get('reward_message','')}

@bp.post('/missions/<mission_id>/snack-run')
@login_required
def start_run(mission_id):
    mission=json.loads(owned(mission_id).payload)
    purchase=eligible_purchase(mission_id,current_user.id)
    run=SnackRun.query.filter_by(mission_id=mission_id).first()
    if run:
        saved=json.loads(run.state)
        if saved['status']=='running':
            saved['started']=purchase.created_at;saved['deadline']=purchase.created_at+mission['metadata']['outbound_m']/(15*.44704)
            if now()>=saved['deadline']:saved['status']='lost'
            run.state=json.dumps(saved);db.session.commit()
        return jsonify(snapshot(run,saved))
    graph=arena(mission);timestamp=now()
    deadline=purchase.created_at+mission['metadata']['outbound_m']/(15*.44704)
    state={'status':'lost' if timestamp>=deadline else 'running','started':purchase.created_at,'last':timestamp,'deadline':deadline,'graph':graph,'player':entity(graph['start']),
           'foods':[dict(entity(i),id=n,speed=1.4+n*.1) for n,i in enumerate(graph['foodStarts'])], 'tap_seq':0,'tap_time':0,'tap_dir':None,'boost':0}
    run=SnackRun(id=str(uuid.uuid4()),mission_id=mission_id,owner_id=current_user.id,state=json.dumps(state))
    try:db.session.add(run);db.session.commit()
    except IntegrityError:
        db.session.rollback();run=SnackRun.query.filter_by(mission_id=mission_id).first()
        if not run:raise
    return jsonify(snapshot(run,json.loads(run.state))),201

@bp.post('/snack-runs/<run_id>/step')
@login_required
def step_run(run_id):
    run=SnackRun.query.filter_by(id=run_id,owner_id=current_user.id).first()
    if not run:fail('not_found','Game not found.',404)
    data=request.get_json(silent=True)
    if not isinstance(data,dict):fail('invalid_input','Use a JSON game input.')
    direction=data.get('direction');seq=data.get('tap_seq',0)
    if (direction is not None and (not isinstance(direction,str) or direction not in {'up','down','left','right'})) or type(seq) is not int or not 0<=seq<=2147483647:fail('invalid_input','Invalid game controls.')
    state=json.loads(run.state);timestamp=now()
    if state['status']=='running':
        purchase=eligible_purchase(run.mission_id,current_user.id)
        mission=json.loads(owned(run.mission_id).payload)
        state['started']=purchase.created_at;state['deadline']=purchase.created_at+mission['metadata']['outbound_m']/(15*.44704)
        # Wall-clock delivery deadline never pauses or resets with the browser.
        if timestamp>=state['deadline']:state['status']='lost'
        else:
            dt=max(0,min(.2,timestamp-state['last']));state['last']=timestamp
            if seq>state['tap_seq']:
                if direction==state['tap_dir'] and timestamp-state['tap_time']<.35:state['boost']=timestamp+.28
                state.update(tap_seq=seq,tap_time=timestamp,tap_dir=direction)
            graph=state['graph'];old=position(graph,state['player'])[1]
            advance(graph,state['player'],(32 if timestamp<state['boost'] else 16)*dt if direction else 0,lambda e:directional(graph,e,direction))
            new=position(graph,state['player'])[1];remaining=[]
            for food in state['foods']:
                before=position(graph,food)[1];advance(graph,food,food['speed']*dt,lambda e:food_next(graph,e));after=position(graph,food)[1]
                # Fixed world-space contact distance; zoom cannot change eligibility.
                if swept(old,new,before,after)>10:remaining.append(food)
            state['foods']=remaining
            if not remaining:
                state['status']='won'
                purchase=eligible_purchase(run.mission_id,current_user.id)
                db.session.add(SnackCoupon(id=str(uuid.uuid4()),owner_id=current_user.id,run_id=run.id,purchase_id=purchase.id,code='SNACK15-'+secrets.token_hex(8).upper(),issued_at=timestamp,expires_at=timestamp+30*86400))
                state['reward_message']='15% coupon saved to your account for your next purchase. One reward per delivery purchase.'
        run.state=json.dumps(state)
        try:db.session.commit()
        except Exception:
            db.session.rollback();fail('game_retry','Game update conflicted. Retry.',409)
    return jsonify(snapshot(run,state))

@bp.get('/coupons')
@login_required
def wallet():
    rows=SnackCoupon.query.filter_by(owner_id=current_user.id).order_by(SnackCoupon.issued_at.desc()).limit(50).all()
    return jsonify(coupons=[coupon_json(c) for c in rows],checkout_connected=True,demo_checkout=bool(current_app.config.get('ALLOW_DEMO_CHECKOUT',False)))

def register_game_rewards(app,limiter):
    register_checkout(app,limiter)
    app.register_blueprint(bp)
    for endpoint,limit in [('snack_rewards.start_run','10 per minute'),('snack_rewards.step_run','900 per minute')]:
        handler=app.view_functions[endpoint]
        def invoke(*args,_handler=handler,**kwargs):return _handler(*args,**kwargs)
        invoke.__name__=endpoint.replace('.','_')
        app.view_functions[endpoint]=limiter.limit(limit)(invoke)
