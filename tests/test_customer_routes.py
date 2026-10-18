"""Routing integration and ownership tests; no real database or hardware used."""
from pathlib import Path
import hashlib
import pytest
from backend.app import create_app
from backend import customer_routes as routes
from backend.map_route_service import PICKUP, DESTINATION

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def client():
    app=create_app({'TESTING':True,'SECRET_KEY':'test-only-secret','SQLALCHEMY_DATABASE_URI':'sqlite://',
                    'RATELIMIT_ENABLED':False,'CUSTOMER_MAP_SOURCE':str(ROOT/'gmu_map_16OCT26.json')})
    return app.test_client()

def token(client):
    return client.get('/api/customer/session').json['csrf_token']

def headers(client,key='request-12345678'):
    return {'X-CSRF-Token':token(client),'Idempotency-Key':key}

def body(**extra):
    return {'destination':{'lat':DESTINATION[0],'lon':DESTINATION[1]},'destination_name':'4504 Overcup Court','confirmed':True,**extra}

def sign_in(client,email='one@example.test'):
    password='TestPassword2026!'
    assert client.post('/api/auth/register',json={'email':email,'password':password}).status_code==201
    assert client.post('/api/auth/login',json={'email':email,'password':password}).status_code==200


def test_known_destination_catalogue(client):
    r=client.get('/api/customer/destinations');assert r.status_code==200
    assert r.json['pickup']['lat']==PICKUP[0]
    assert r.json['destinations'][0]['lon']==DESTINATION[1]

def test_exact_route_reuses_dijkstra(client):
    r=client.post('/api/customer/routes/preview',json=body(),headers=headers(client))
    assert r.status_code==200
    m=r.json['metadata'];assert 2600<m['outbound_m']<2700
    assert m['destination_snap_m']<4
    assert m['simulated'] is True and m['robot_navigation_approved'] is False
    assert m['simulation_speed_mph']==15
    assert 390<m['delivery_eta_seconds']<400
    assert [f['properties']['leg'] for f in r.json['features']]==['outbound','return']

@pytest.mark.parametrize('point',[{'lat':True,'lon':-77.3},{'lat':'38.8','lon':-77.3},{'lat':91,'lon':0},{'lat':38},None])
def test_invalid_coordinates_rejected(client,point):
    r=client.post('/api/customer/routes/preview',json=body(destination=point),headers=headers(client));assert r.status_code==400

def test_off_network_destination_rejected(client):
    r=client.post('/api/customer/routes/preview',json=body(destination={'lat':0,'lon':0}),headers=headers(client))
    assert r.status_code==422 and r.json['code']=='excessive_snap'

def test_same_pickup_rejected(client):
    r=client.post('/api/customer/routes/preview',json=body(destination={'lat':PICKUP[0],'lon':PICKUP[1]}),headers=headers(client))
    assert r.status_code==422 and r.json['code']=='same_endpoint'

def test_disconnected_failure_clear(client,monkeypatch):
    def disconnected(*args,**kwargs):raise ValueError('No connected out-and-return route. No straight connectors added.')
    monkeypatch.setattr(routes,'make_mission',disconnected)
    r=client.post('/api/customer/routes/preview',json=body(),headers=headers(client))
    assert r.status_code==422 and r.json['code']=='disconnected_route'

def test_missing_map_fails_closed(client,tmp_path):
    client.application.config['CUSTOMER_MAP_SOURCE']=str(tmp_path/'missing.json')
    r=client.post('/api/customer/routes/preview',json=body(),headers=headers(client))
    assert r.status_code==503 and r.json['code']=='map_unavailable'

def test_csrf_required(client):
    r=client.post('/api/customer/routes/preview',json=body());assert r.status_code==403

def test_cross_origin_rejected(client):
    r=client.post('/api/customer/routes/preview',json=body(),headers={**headers(client),'Origin':'https://other.example'})
    assert r.status_code==403 and r.json['code']=='origin_rejected'

def test_save_requires_login(client):
    r=client.post('/api/customer/missions',json=body(),headers=headers(client));assert r.status_code==401

def test_confirmation_required(client):
    sign_in(client);r=client.post('/api/customer/missions',json=body(confirmed=False),headers=headers(client))
    assert r.status_code==400 and r.json['code']=='confirmation_required'

def test_key_required(client):
    sign_in(client);r=client.post('/api/customer/missions',json=body(),headers={'X-CSRF-Token':token(client)})
    assert r.status_code==400 and r.json['code']=='request_key_required'

def test_owner_can_save_read_and_list(client):
    sign_in(client);r=client.post('/api/customer/missions',json=body(reference='lunch'),headers=headers(client));assert r.status_code==201
    mid=r.json['mission_id'];assert client.get('/api/customer/missions/'+mid).json['reference']=='lunch'
    assert client.get('/api/customer/missions').json['missions'][0]['mission_id']==mid

def test_other_account_cannot_read_mission(client):
    sign_in(client);r=client.post('/api/customer/missions',json=body(),headers=headers(client));mid=r.json['mission_id']
    client.post('/api/auth/logout');sign_in(client,'two@example.test')
    assert client.get('/api/customer/missions/'+mid).status_code==404
    assert client.get('/api/customer/missions').json['missions']==[]

def test_retry_does_not_create_duplicate(client):
    sign_in(client);h=headers(client)
    a=client.post('/api/customer/missions',json=body(),headers=h)
    b=client.post('/api/customer/missions',json=body(),headers=h)
    assert a.status_code==201 and b.status_code==200 and b.json['replayed']
    assert a.json['mission_id']==b.json['mission_id']
    assert len(client.get('/api/customer/missions').json['missions'])==1

def test_key_reuse_with_other_destination_rejected(client):
    sign_in(client);h=headers(client);client.post('/api/customer/missions',json=body(),headers=h)
    r=client.post('/api/customer/missions',json=body(destination_name='Changed label'),headers=h)
    assert r.status_code==409

def test_shared_source_files_unchanged(client):
    paths=[ROOT/'gmu_map_16OCT26.json',ROOT/'html/web/public/data/mission-route.json']
    before={p:hashlib.sha256(p.read_bytes()).digest() for p in paths if p.exists()}
    sign_in(client);client.post('/api/customer/missions',json=body(),headers=headers(client))
    assert before=={p:hashlib.sha256(p.read_bytes()).digest() for p in before}

def test_cannot_supply_unconfirmed_route_geometry(client):
    r=client.post('/api/customer/routes/preview',json={**body(),'features':[{'fake':'route'}]},headers=headers(client))
    assert r.status_code==200 and r.json['features'][0]['geometry']['type']=='LineString'
    assert r.json['features'][0]['properties']['length_m']>2600

def test_invalid_json_rejected(client):
    r=client.post('/api/customer/routes/preview',data='{',content_type='application/json',headers=headers(client))
    assert r.status_code==400 and r.json['code']=='invalid_request'

def test_bad_json_source_fails_closed(client,tmp_path):
    p=tmp_path/'bad.json';p.write_text('{');client.application.config['CUSTOMER_MAP_SOURCE']=str(p)
    r=client.post('/api/customer/routes/preview',json=body(),headers=headers(client))
    assert r.status_code==503 and r.json['code']=='map_unavailable'

def test_rate_limit_returns_clear_json():
    app=create_app({'TESTING':True,'SECRET_KEY':'rate-test','SQLALCHEMY_DATABASE_URI':'sqlite://','RATELIMIT_ENABLED':True})
    c=app.test_client();h=headers(c)
    for _ in range(10):assert c.post('/api/customer/routes/preview',json={},headers=h).status_code==400
    r=c.post('/api/customer/routes/preview',json={},headers=h)
    assert r.status_code==429 and r.json['code']=='rate_limited'

def test_same_workspace_server_preserves_assets_and_database(tmp_path,monkeypatch):
    import sqlite3
    import run_customer_preview as runner
    monkeypatch.setattr(runner,'root',tmp_path)
    import backend.app as backend_app
    monkeypatch.setattr(backend_app,'__file__',str(tmp_path/'backend/app.py'))
    public=tmp_path/'html/web/public';public.mkdir(parents=True)
    css=tmp_path/'html/web/css';css.mkdir(parents=True);(css/'styles.css').write_text('body{color:purple}')
    data=public/'data';data.mkdir();(data/'mission-route.json').write_text('{"original":true}')
    public.joinpath('MapAPI.html').write_text('<h1>Existing map</h1>')
    public.joinpath('audio').mkdir();public.joinpath('audio/test.mp3').write_bytes(b'test audio asset')
    private=tmp_path/'instance';private.mkdir();database=private/'max_byte.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE existing_data (value TEXT)');db.execute("INSERT INTO existing_data VALUES ('preserved')")
    app=runner.make_local_app();c=app.test_client()
    assert c.get('/MapAPI.html').data==b'<h1>Existing map</h1>'
    assert c.get('/css/styles.css').data==b'body{color:purple}'
    assert c.get('/data/mission-route.json').json=={'original':True}
    assert c.get('/audio/test.mp3').status_code==200
    assert c.get('/api/health').json['status']=='ok'
    assert c.get('/css/secret.py').status_code==404
    with sqlite3.connect(database) as db:assert db.execute('SELECT value FROM existing_data').fetchone()[0]=='preserved'
    backups=list((tmp_path/'customer-routing-db-backups').glob('*.db'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as db:assert db.execute('SELECT value FROM existing_data').fetchone()[0]=='preserved'
