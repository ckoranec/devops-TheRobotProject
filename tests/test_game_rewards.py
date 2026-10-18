"""Verify authoritative movement, ownership, deadline and account wallet rules."""
from pathlib import Path
import json
import pytest
from backend.app import create_app, db
from backend import game_rewards as rewards

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture
def setup():
    clock=[1800000000.0]
    app=create_app({'TESTING':True,'SECRET_KEY':'test-only','SQLALCHEMY_DATABASE_URI':'sqlite://','RATELIMIT_ENABLED':False,'CUSTOMER_MAP_SOURCE':str(ROOT/'gmu_map_16OCT26.json'),'SNACK_NETWORK_SOURCE':str(ROOT/'html/web/public/data/mission-network.json'),'SNACK_CLOCK':lambda:clock[0],'ALLOW_DEMO_CHECKOUT':True})
    c=app.test_client();password='Testing-Password-2026'
    def login(email):
        c.post('/api/auth/register',json={'email':email,'password':password})
        assert c.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
    login('one@example.test')
    def headers():return {'X-CSRF-Token':c.get('/api/customer/session').json['csrf_token']}
    m=c.post('/api/customer/missions',json={'destination':{'lat':38.8299577,'lon':-77.2951851},'confirmed':True},headers={**headers(),'Idempotency-Key':'reward-mission-1'}).json['mission_id']
    purchase=c.post('/api/customer/checkout/complete',json={'mission_id':m,'items':[{'sku':'campus-classic','quantity':1}]},headers={**headers(),'Idempotency-Key':'initial-purchase-1'})
    assert purchase.status_code==201,purchase.json
    m=purchase.json['mission_id']
    return app,c,clock,headers,m,login

def start(s):
    _,c,_,h,m,_=s;r=c.post('/api/customer/missions/'+m+'/snack-run',json={},headers=h());assert r.status_code in (200,201);return r.json

def test_game_start_and_idempotency(setup):
    a=start(setup);b=start(setup);assert a['run_id']==b['run_id'];assert a['caught']==0 and len(a['foods'])==5

def test_client_score_does_not_award(setup):
    _,c,clock,h,_,_=setup;r=start(setup);clock[0]+=.1
    result=c.post('/api/customer/snack-runs/'+r['run_id']+'/step',json={'direction':None,'caught':5,'won':True},headers=h())
    assert result.json['caught']==0 and result.json['coupon'] is None
    assert c.get('/api/customer/coupons').json['coupons']==[]

def test_wall_clock_deadline_cannot_reset(setup):
    _,c,clock,h,_,_=setup;r=start(setup);clock[0]+=500
    result=c.post('/api/customer/snack-runs/'+r['run_id']+'/step',json={},headers=h())
    assert result.json['state']=='lost' and result.json['coupon'] is None
    assert start(setup)['state']=='lost'

def test_other_account_cannot_read_game_or_coupon(setup):
    _,c,_,h,m,login=setup;r=start(setup);login('two@example.test')
    assert c.post('/api/customer/snack-runs/'+r['run_id']+'/step',json={},headers=h()).status_code==404
    assert c.post('/api/customer/missions/'+m+'/snack-run',json={},headers=h()).status_code==404
    assert c.get('/api/customer/coupons').json['coupons']==[]

@pytest.mark.parametrize('bad',[['up'],{},12,'north'])
def test_bad_direction_is_json_error(setup,bad):
    _,c,_,h,_,_=setup;r=start(setup)
    result=c.post('/api/customer/snack-runs/'+r['run_id']+'/step',json={'direction':bad},headers=h())
    assert result.status_code==400

def test_motion_is_bounded_by_server_time(setup):
    app,c,clock,h,_,_=setup;r=start(setup)
    clock[0]+=20
    result=c.post('/api/customer/snack-runs/'+r['run_id']+'/step',json={'direction':'up','speed':99999},headers=h()).json
    from backend.dijkstra_json import haversine
    assert haversine(*r['player'],*result['player'])<=3.3

def test_server_final_contact_awards_once_and_wallet_persists(setup):
    app,c,clock,h,_,_=setup;r=start(setup)
    # Arrange a final real contact in server storage, never via the public API.
    with app.app_context():
        run=db.session.get(rewards.SnackRun,r['run_id']);state=json.loads(run.state)
        state['foods']=[dict(rewards.entity(state['player']['node']),id=4,speed=0)]
        run.state=json.dumps(state);db.session.commit()
    clock[0]+=.1
    url='/api/customer/snack-runs/'+r['run_id']+'/step'
    result=c.post(url,json={},headers=h()).json
    assert result['state']=='won' and result['caught']==5
    assert result['coupon']['percent_off']==15 and result['coupon']['checkout_connected'] is True
    again=c.post(url,json={},headers=h()).json
    assert again['coupon']['code']==result['coupon']['code']
    assert len(c.get('/api/customer/coupons').json['coupons'])==1

def test_mutations_need_csrf(setup):
    _,c,_,_,m,_=setup
    assert c.post('/api/customer/missions/'+m+'/snack-run',json={}).status_code==403

def test_game_requires_same_map_version(setup,tmp_path):
    app,c,_,h,m,_=setup
    p=tmp_path/'network.json';p.write_text('{"map_sha256":"wrong"}')
    app.config['SNACK_NETWORK_SOURCE']=str(p)
    r=c.post('/api/customer/missions/'+m+'/snack-run',json={},headers=h())
    assert r.status_code==409 and r.json['code']=='stale_game_map'
