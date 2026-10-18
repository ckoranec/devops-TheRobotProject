"""A no-charge public demo must finish checkout before its delivery clock starts."""
import uuid
import json
import pytest
from backend.app import db
from backend.customer_routes import CustomerMission
from backend.purchase_checkout import DemoPayment,DeliveryPurchase
from test_game_rewards import setup

def cart(s):
    app=s[0]
    with app.app_context():mission=CustomerMission.query.filter_by(request_key='reward-mission-1').first().id
    return {'mission_id':mission,'items':[{'sku':'campus-classic','quantity':1}]}
def payment(s,**extra):
    return s[1].post('/api/customer/checkout/demo-payment',json={**cart(s),**extra},headers={**s[3](),'Idempotency-Key':str(uuid.uuid4())})
def confirm(s,identity):return s[1].post('/api/customer/checkout/demo-payment/'+identity+'/confirm',json={},headers=s[3]())
def count(s):
    with s[0].app_context():return DeliveryPurchase.query.count()

def test_review_does_not_dispatch_and_confirmation_does(setup):
    before=count(setup);p=payment(setup);assert p.status_code==201,p.json
    assert p.json['status']=='awaiting_confirmation' and p.json['charged_cents']==0
    assert count(setup)==before
    assert setup[1].get('/api/customer/missions/'+cart(setup)['mission_id']+'/delivery').status_code==409
    setup[2][0]+=30
    result=confirm(setup,p.json['payment_id']);assert result.status_code==201,result.json
    assert result.json['payment_status']=='succeeded_simulated' and result.json['charged_cents']==0
    assert result.json['status']=='demo_confirmed' and result.json['map_url'].startswith('MapAPI.html?mission=')
    assert result.json['dispatch_started_at']==setup[2][0] and count(setup)==before+1
    state=setup[1].get('/api/customer/missions/'+result.json['mission_id']+'/delivery').json
    assert state['phase']=='outbound' and state['distance_m']==0 and state['speed_mph']==15

def test_delivery_arrives_returns_and_survives_refresh(setup):
    result=confirm(setup,payment(setup).json['payment_id']).json;url='/api/customer/missions/'+result['mission_id']+'/delivery'
    initial=setup[1].get(url).json;start=setup[2][0]
    setup[2][0]=start+initial['outbound_m']/(15*.44704)+5
    returned=setup[1].get(url).json;assert returned['phase']=='returning' and returned['delivery_eta_seconds']==0
    assert setup[1].get(url).json['started_at']==initial['started_at']
    setup[2][0]=start+initial['total_m']/(15*.44704)+5
    completed=setup[1].get(url).json;assert completed['phase']=='returned' and completed['distance_m']==completed['total_m']
    assert completed['return_eta_seconds']==0

def test_confirmation_retry_never_creates_another_purchase(setup):
    p=payment(setup).json;before=count(setup);a=confirm(setup,p['payment_id']);b=confirm(setup,p['payment_id'])
    assert a.status_code==201 and b.status_code==200
    assert a.json['purchase_id']==b.json['purchase_id'] and a.json['mission_id']==b.json['mission_id']
    assert b.json['replayed'] is True and count(setup)==before+1

def test_payment_session_is_account_owned(setup):
    p=payment(setup).json;setup[5]('second-payment@example.test')
    assert confirm(setup,p['payment_id']).status_code==404

def test_expired_unconfirmed_payment_creates_no_purchase(setup):
    p=payment(setup).json;before=count(setup);setup[2][0]+=901
    response=confirm(setup,p['payment_id']);assert response.status_code==409 and response.json['code']=='payment_expired'
    assert count(setup)==before

def test_browser_total_or_paid_flag_cannot_create_a_real_charge(setup):
    p=payment(setup,total_cents=0,paid=True,charged_cents=999999).json
    assert p['total_cents']==898 and p['charged_cents']==0
    result=confirm(setup,p['payment_id']).json
    with setup[0].app_context():
        saved=db.session.get(DeliveryPurchase,result['purchase_id'])
        assert saved.status=='demo_confirmed' and saved.payment_reference.startswith('DEMO-')
    assert result['charged_cents']==0 and result['payment_simulated'] is True

def test_payment_creation_retry_and_changed_cart(setup):
    h={**setup[3](),'Idempotency-Key':'same-demo-payment-key'};data=cart(setup)
    a=setup[1].post('/api/customer/checkout/demo-payment',json=data,headers=h)
    b=setup[1].post('/api/customer/checkout/demo-payment',json=data,headers=h)
    assert a.json['payment_id']==b.json['payment_id'] and b.json['replayed']
    c=setup[1].post('/api/customer/checkout/demo-payment',json={**data,'items':[{'sku':'campus-classic','quantity':2}]},headers=h)
    assert c.status_code==409

def test_game_uses_payment_dispatch_deadline_not_play_click(setup):
    result=confirm(setup,payment(setup).json['payment_id']).json;setup[2][0]+=30
    game=setup[1].post('/api/customer/missions/'+result['mission_id']+'/snack-run',json={},headers=setup[3]())
    assert game.status_code==201 and game.json['elapsed_seconds']==30
    delivery=setup[1].get('/api/customer/missions/'+result['mission_id']+'/delivery').json
    assert game.json['delivery_eta_seconds']==pytest.approx(delivery['delivery_eta_seconds'])

def test_first_game_after_delivery_is_lost_without_coupon(setup):
    result=confirm(setup,payment(setup).json['payment_id']).json
    delivery=setup[1].get('/api/customer/missions/'+result['mission_id']+'/delivery').json
    setup[2][0]+=delivery['delivery_eta_seconds']+1
    game=setup[1].post('/api/customer/missions/'+result['mission_id']+'/snack-run',json={},headers=setup[3]())
    assert game.json['state']=='lost' and game.json['coupon'] is None

def test_guest_cannot_confirm_or_start_delivery(setup):
    guest=setup[0].test_client();token=guest.get('/api/customer/session').json['csrf_token']
    r=guest.post('/api/customer/checkout/demo-payment',json=cart(setup),headers={'X-CSRF-Token':token,'Idempotency-Key':'guest-payment-key'})
    assert r.status_code==401
    assert guest.get('/api/customer/missions/'+setup[4]+'/delivery').status_code==401

def test_demo_mode_can_be_disabled_without_recording_payment(setup):
    p=payment(setup).json;before=count(setup);setup[0].config['ALLOW_DEMO_CHECKOUT']=False
    assert confirm(setup,p['payment_id']).status_code==503
    assert count(setup)==before

def test_failed_confirmation_commit_leaves_no_partial_dispatch(setup,monkeypatch):
    pending=payment(setup).json;before=count(setup)
    def fail_commit():raise RuntimeError('test commit interruption')
    with monkeypatch.context() as patch:
        patch.setattr(db.session,'commit',fail_commit)
        with pytest.raises(RuntimeError):confirm(setup,pending['payment_id'])
    assert count(setup)==before
    with setup[0].app_context():
        saved=db.session.get(DemoPayment,pending['payment_id']);assert saved.purchase_id is None
    retried=confirm(setup,pending['payment_id']);assert retried.status_code==201 and count(setup)==before+1

def test_legacy_running_game_cannot_keep_a_later_deadline(setup):
    from backend.game_rewards import SnackRun
    result=confirm(setup,payment(setup).json['payment_id']).json
    game=setup[1].post('/api/customer/missions/'+result['mission_id']+'/snack-run',json={},headers=setup[3]()).json
    delivery=setup[1].get('/api/customer/missions/'+result['mission_id']+'/delivery').json
    with setup[0].app_context():
        run=db.session.get(SnackRun,game['run_id']);state=json.loads(run.state);state['deadline']+=10000;run.state=json.dumps(state);db.session.commit()
    setup[2][0]+=delivery['delivery_eta_seconds']+1
    resumed=setup[1].post('/api/customer/missions/'+result['mission_id']+'/snack-run',json={},headers=setup[3]()).json
    assert resumed['state']=='lost' and resumed['coupon'] is None
