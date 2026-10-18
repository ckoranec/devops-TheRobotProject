"""The public demo entrypoint permits simulated checkout but never real payments."""
from pathlib import Path
import importlib.util

def test_public_demo_entry_never_enables_real_payments(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.setenv('MAX_BYTE_SECRET_KEY','production-entry-test-secret-'*3)
    monkeypatch.setenv('MAX_BYTE_DATABASE_URI','sqlite:///'+str(tmp_path/'production-test.db'))
    spec=importlib.util.spec_from_file_location('verified_production_entry',root/'wsgi.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    client=module.app.test_client()
    response=client.get('/api/health')
    assert response.status_code==200 and response.json['status']=='ok'
    assert response.headers['Cache-Control']=='no-store'
    catalogue=client.get('/api/customer/checkout/catalogue')
    assert catalogue.status_code==200
    assert catalogue.json['demo_checkout'] is True
    assert catalogue.json['payment_connected'] is False
    release=client.get('/api/release')
    assert release.json['payments_enabled'] is False
    assert release.json['demonstration_site'] is True
    assert module.app.config['ALLOW_DEMO_CHECKOUT'] is True
