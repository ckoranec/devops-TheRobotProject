"""Private production entrypoint. Never run the local demo runner on the server."""
import os
from pathlib import Path
from flask import request
from werkzeug.middleware.proxy_fix import ProxyFix
from backend.app import create_app
secret=os.environ.get('MAX_BYTE_SECRET_KEY','')
uri=os.environ.get('MAX_BYTE_DATABASE_URI','')
if len(secret)<32 or not uri:
    raise RuntimeError('Persistent production secret and database URI are required.')
root=Path(__file__).resolve().parent
app=create_app({'SECRET_KEY':secret,'SQLALCHEMY_DATABASE_URI':uri,
                'CUSTOMER_MAP_SOURCE':str(root/'gmu_map_16OCT26.json'),
                'SNACK_NETWORK_SOURCE':str(root/'html/web/public/data/mission-network.json'),
                'ALLOW_DEMO_CHECKOUT':False,
                'SESSION_COOKIE_SECURE':os.environ.get('MAX_BYTE_HTTPS_ONLY')=='1'})
# The API binds loopback only; Nginx supplies exactly one trusted proxy hop.
app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=0,x_port=0)
@app.after_request
def private_api_response(response):
    if request.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response
@app.get('/api/release')
def release_info():
    from flask import jsonify
    return jsonify(commit=root.name,simulated=True,payments_enabled=False)
