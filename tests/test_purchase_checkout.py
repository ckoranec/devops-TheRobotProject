"""Fresh customer flow and per-purchase reward/checkout regression checks."""
import json
import uuid
import pytest
from backend.app import db
from backend import game_rewards as rewards
from backend.purchase_checkout import DeliveryPurchase,PurchaseCoupon
from test_game_rewards import setup, start

def buy(s,**changes):
    _,c,_,h,m,_=s
    data={'mission_id':m,'items':[{'sku':'campus-classic','quantity':1}],**changes}
    return c.post('/api/customer/checkout/complete',json=data,headers={**h(),'Idempotency-Key':str(uuid.uuid4())})

def win(s,mission):
    app,c,clock,h,_,_=s
    r=c.post('/api/customer/missions/'+mission+'/snack-run',json={},headers=h());assert r.status_code in (200,201),r.json
    run_id=r.json['run_id']
    # Server-state arrangement exercises final collision, never a public score flag.
    with app.app_context():
        run=db.session.get(rewards.SnackRun,run_id);state=json.loads(run.state)
        state['foods']=[dict(rewards.entity(state['player']['node']),id=4,speed=0)]
        run.state=json.dumps(state);db.session.commit()
    clock[0]+=.1
    r=c.post('/api/customer/snack-runs/'+run_id+'/step',json={},headers=h());assert r.status_code==200,r.json
    assert r.json['state']=='won';return r.json['coupon']

def test_each_purchase_gets_a_new_attempt_and_coupon_same_day(setup):
    first=start(setup);a=win(setup,setup[4]);purchase=buy(setup)
    assert purchase.status_code==201
    second=win(setup,purchase.json['mission_id'])
    assert second['code']!=a['code']
    assert len(setup[1].get('/api/customer/coupons').json['coupons'])==2
    again=start(setup);assert again['run_id']==first['run_id'] and again['state']=='won'

def test_quote_and_atomic_redemption_on_next_purchase(setup):
    _,c,_,h,_,_=setup;coupon=win(setup,setup[4]);data={'mission_id':setup[4],'items':[{'sku':'campus-classic','quantity':1}],'coupon_code':coupon['code']}
    quote=c.post('/api/customer/checkout/quote',json=data,headers=h())
    assert quote.status_code==200
    assert quote.json['subtotal_cents']==699 and quote.json['discount_cents']==105
    assert quote.json['total_cents']==793
    result=buy(setup,coupon_code=coupon['code']);assert result.status_code==201
    duplicate=buy(setup,coupon_code=coupon['code']);assert duplicate.status_code==409
    wallet=c.get('/api/customer/coupons').json['coupons'];assert wallet[0]['status']=='redeemed'

def test_saved_route_alone_does_not_grant_game(setup):
    app,c,_,h,_,_=setup
    with app.app_context():
        from backend.customer_routes import CustomerMission
        original=CustomerMission.query.filter_by(request_key='reward-mission-1').first();identity=original.id
    r=c.post('/api/customer/missions/'+identity+'/snack-run',json={},headers=h())
    assert r.status_code==409 and r.json['code']=='purchase_required'

def test_checkout_retry_is_one_purchase(setup):
    _,c,_,h,m,_=setup;headers={**h(),'Idempotency-Key':'retry-same-checkout'};data={'mission_id':m,'items':[{'sku':'campus-classic','quantity':1}]}
    a=c.post('/api/customer/checkout/complete',json=data,headers=headers)
    b=c.post('/api/customer/checkout/complete',json=data,headers=headers)
    assert a.status_code==201 and b.status_code==200
    assert a.json['purchase_id']==b.json['purchase_id'] and a.json['mission_id']==b.json['mission_id']
    changed=c.post('/api/customer/checkout/complete',json={**data,'items':[{'sku':'campus-classic','quantity':2}]},headers=headers)
    assert changed.status_code==409

@pytest.mark.parametrize('items',[[{'sku':'missing','quantity':1}],[{'sku':'campus-classic','quantity':True}],[{'sku':'campus-classic','quantity':0}],[{'sku':'campus-classic','quantity':99}],[]])
def test_invalid_cart_is_rejected(setup,items):
    assert buy(setup,items=items).status_code==400

def test_prices_and_paid_flag_cannot_be_supplied_by_browser(setup):
    app,c,_,h,m,_=setup
    data={'mission_id':m,'items':[{'sku':'campus-classic','quantity':1,'price_cents':1}],'paid':True,'total_cents':1}
    r=c.post('/api/customer/checkout/complete',json=data,headers={**h(),'Idempotency-Key':'tampered-price-1'})
    assert r.status_code==201 and r.json['total_cents']==898 and r.json['status']=='demo_confirmed'
    app.config['ALLOW_DEMO_CHECKOUT']=False
    assert buy(setup,paid=True).status_code==503

def test_other_customer_cannot_redeem_coupon_or_checkout_other_mission(setup):
    _,c,_,h,m,login=setup;coupon=win(setup,m);login('next-customer@example.test')
    assert c.get('/api/customer/coupons').json['coupons']==[]
    assert buy(setup,coupon_code=coupon['code']).status_code==404
    # Own route, stolen coupon: still rejected.
    r=c.post('/api/customer/missions',json={'destination':{'lat':38.8299577,'lon':-77.2951851},'confirmed':True},headers={**h(),'Idempotency-Key':'second-account-route'})
    result=c.post('/api/customer/checkout/quote',json={'mission_id':r.json['mission_id'],'items':[{'sku':'campus-classic','quantity':1}],'coupon_code':coupon['code']},headers=h())
    assert result.status_code==422

def test_expired_coupon_is_not_redeemed(setup):
    _,c,clock,h,m,_=setup;coupon=win(setup,m);clock[0]+=31*86400
    r=buy(setup,coupon_code=coupon['code']);assert r.status_code==422

def test_production_default_does_not_complete_fake_purchases(setup):
    app,c,_,h,m,_=setup;app.config.pop('ALLOW_DEMO_CHECKOUT',None)
    assert buy(setup).status_code==503
    assert c.get('/api/customer/checkout/catalogue').json['demo_checkout'] is False

def test_verified_paid_purchase_can_play_without_demo_mode(setup):
    app,c,_,h,m,_=setup
    with app.app_context():
        purchase=DeliveryPurchase.query.filter_by(mission_id=m).first()
        purchase.status='paid';purchase.payment_reference='verified-provider-fixture';db.session.commit()
    app.config['ALLOW_DEMO_CHECKOUT']=False
    result=start(setup);assert result['state']=='running'

def test_unconfirmed_or_cancelled_purchase_cannot_start_game(setup):
    app,c,_,h,m,_=setup
    with app.app_context():
        purchase=DeliveryPurchase.query.filter_by(mission_id=m).first();purchase.status='cancelled';db.session.commit()
    r=c.post('/api/customer/missions/'+m+'/snack-run',json={},headers=h())
    assert r.status_code==409 and r.json['code']=='purchase_required'
