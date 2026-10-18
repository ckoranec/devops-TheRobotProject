"""Deploy an exact approved DevOps commit. Keep MySQL/port 3000 untouched.
Run as root on the known Ubuntu server. Bootstrap the private account DB once;
subsequent releases retain live records. Roll back API/config/static activation
on verification failure. Never deploy the localhost demo runner.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import fcntl
import hashlib
import io
import json
import os
import pwd
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
import urllib.request
import urllib.error

parser=argparse.ArgumentParser();parser.add_argument('commit');parser.add_argument('--bootstrap-db',required=True);args=parser.parse_args()
if os.geteuid()!=0:raise SystemExit('Run on the server as root.')
if not re.fullmatch('[0-9a-f]{40}',args.commit):raise SystemExit('Expected a full approved commit SHA.')
# Prevent two root deployments from modifying the same release concurrently.
lock=Path('/root/.max-byte-api-deploy.lock').open('a');os.chmod(lock.name,0o600)
try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Another MAX Byte deployment is running. Nothing changed.')
commit=args.commit;repo=Path('/var/www/html/devops-TheRobotProject');web=Path('/var/www/html')
package=Path(__file__).resolve().parent;home=Path('/opt/max-byte-api');data=Path('/var/lib/max-byte-api');dbfile=data/'max_byte.db'
site=Path('/etc/nginx/sites-enabled/digitalocean').resolve();unit=Path('/etc/systemd/system/max-byte-api.service');envfile=Path('/etc/max-byte-api.env');proxy=Path('/etc/nginx/max-byte-api/location.conf');current=home/'current'
marker=home/'managed.json';managed='MAX_BYTE_API_MANAGED_V33'
def run(argv,**kwargs):return subprocess.run(argv,check=True,**kwargs)
def output(argv):return subprocess.check_output(argv,text=True,stderr=subprocess.PIPE)
def connectable(port):
    with socket.socket() as sock:sock.settimeout(.5);return sock.connect_ex(('127.0.0.1',port))==0
def http(path,timeout=15):
    request=urllib.request.Request('http://127.0.0.1/'+path,headers={'Host':'138.197.107.244'})
    with urllib.request.urlopen(request,timeout=timeout) as response:return response.read()
def write_atomic(path,content,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.max-byte-new');temp.write_bytes(content);temp.chmod(mode);os.replace(temp,path)

git=['git','-c','safe.directory='+str(repo),'-C',str(repo)]
if not repo.is_dir() or not site.is_file():raise SystemExit('Expected repository/Nginx site not found. No live changes made.')
run(['nginx','-t'])
run(git+['fetch','origin','DevOps'])
if output(git+['rev-parse','FETCH_HEAD']).strip()!=commit:raise SystemExit('Approved SHA differs from GitHub DevOps. No deployment.')
site_original=site.read_bytes();text=site_original.decode()
if len(re.findall(r'(?m)^\s*root\s+/var/www/html\s*;',text))!=1:raise SystemExit('Unexpected Nginx site structure. No deployment.')
for path in [unit,envfile,proxy]:
    if path.exists() and (not marker.exists() or (path!=envfile and managed not in path.read_text())):raise SystemExit('Existing unrecognized API configuration: '+str(path))
if current.exists() and (not current.is_symlink() or not marker.exists()):raise SystemExit('Existing unrecognized API release path.')
if connectable(8000) and not (marker.exists() and unit.exists()):raise SystemExit('Loopback port 8000 is occupied by another service. Nothing stopped.')
# Abort if another API route exists; do not replace an existing team application.
nginx_all=output(['nginx','-T'])
without_ours=nginx_all
if proxy.exists():without_ours=without_ours.replace(proxy.read_text(),'')
if re.search(r'location\s+(?:[=~*^]+\s+)?[\"\']?/api(?:/|\b)',without_ours):raise SystemExit('An existing /api location needs reconciliation. Nothing replaced.')
if dbfile.exists() and not marker.exists():raise SystemExit('Private database already exists without our deployment record. Nothing overwritten.')
bootstrap=Path(args.bootstrap_db)
if not dbfile.exists():
    if not bootstrap.is_file():raise SystemExit('Initial private account snapshot required. No database created.')
    with sqlite3.connect('file:'+str(bootstrap)+'?mode=ro',uri=True) as check:
        if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Account snapshot integrity check failed.')
        tables={row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'users' not in tables:raise SystemExit('The snapshot has no project accounts table.')

print('Preparing approved private release. MySQL and port 3000 are unchanged.',flush=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');backup=Path('/root')/('max-byte-api-release-backup-'+stamp);backup.mkdir(mode=0o700)
home.mkdir(parents=True,exist_ok=True);(home/'releases').mkdir(exist_ok=True)
# Mark our own resources before a retry; never use this to adopt another service.
if not marker.exists():marker.write_text(json.dumps({'manager':managed,'created':stamp}));marker.chmod(0o600)
archive=subprocess.check_output(git+['archive','--format=tar',commit]);release=home/'releases'/commit
if release.exists():
    if not (release/'.release-complete').is_file():raise SystemExit('Incomplete release directory exists. Preserve it and inspect before retry.')
else:
    staging=home/'releases'/('.staging-'+stamp);staging.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            rel=Path(member.name)
            if rel.is_absolute() or '..' in rel.parts or member.issym() or member.islnk():raise SystemExit('Unexpected archive path/link.')
            if member.isdir():(staging/rel).mkdir(parents=True,exist_ok=True)
            elif member.isfile():
                destination=staging/rel;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(source.extractfile(member).read());destination.chmod(0o644)
    required=['backend/app.py','backend/customer_routes.py','backend/game_rewards.py','backend/purchase_checkout.py','backend/menu_catalogue.json','wsgi.py','requirements-live.txt','gmu_map_16OCT26.json','html/web/public/data/mission-network.json']
    if any(not (staging/name).is_file() for name in required):raise SystemExit('Approved commit lacks required private API files.')
    (staging/'instance').mkdir(exist_ok=True)
    # A release-local venv keeps dependencies isolated from the server's services.
    venv=staging/'.venv'
    # Reuse already-installed dependencies when the reviewed requirements match.
    reusable=None
    for completed in sorted((home/'releases').glob('*/.release-complete')):
        prior=completed.parent
        if ((prior/'requirements-live.txt').is_file() and
            (prior/'requirements-live.txt').read_bytes()==(staging/'requirements-live.txt').read_bytes() and
            (prior/'.venv/bin/python').exists()):
            reusable=prior/'.venv';break
    if reusable:
        shutil.copytree(reusable,venv,symlinks=True)
        print('Reusing installed production dependencies; no package download required.',flush=True)
    else:
        created=subprocess.run([sys.executable,'-m','venv',str(venv)],capture_output=True)
        if created.returncode:
            raise RuntimeError('Python venv unavailable. Existing live site was not changed.')
        run([str(venv/'bin/python'),'-m','pip','install','-r',str(staging/'requirements-live.txt')])
    # Venv console shebangs include the staging path; use python -m gunicorn after rename.
    (staging/'.release-complete').write_text(commit);staging.rename(release)

try:account=pwd.getpwnam('maxbyte-api')
except KeyError:
    run(['useradd','--system','--home-dir',str(data),'--shell','/usr/sbin/nologin','maxbyte-api']);account=pwd.getpwnam('maxbyte-api')
data.mkdir(parents=True,exist_ok=True);data.chmod(0o700);os.chown(data,account.pw_uid,account.pw_gid)
if dbfile.exists():
    with sqlite3.connect(dbfile) as source,sqlite3.connect(backup/'accounts-before.db') as saved:source.backup(saved)
    (backup/'accounts-before.db').chmod(0o600)
else:
    with sqlite3.connect('file:'+str(bootstrap)+'?mode=ro',uri=True) as source,sqlite3.connect(dbfile) as saved:source.backup(saved)
    print('Initial local account snapshot imported into the private API database.',flush=True)
os.chown(dbfile,account.pw_uid,account.pw_gid);dbfile.chmod(0o600)
# Preserve the existing production secret on every later deployment.
if not envfile.exists():write_atomic(envfile,('MAX_BYTE_SECRET_KEY='+secrets.token_hex(32)+'\nMAX_BYTE_DATABASE_URI=sqlite:////var/lib/max-byte-api/max_byte.db\nPYTHONDONTWRITEBYTECODE=1\n').encode(),0o600)

assets=['MapAPI.html', 'tracking.html', 'index.html', 'menu.html', 'order.html', 'delivery-location.html', 'delivery-location.js', 'coupon-wallet.html', 'coupon-wallet.js', 'purchase-checkout.js', 'customer-pages.css', 'customer-navigation.js', 'map-personality.js', 'robot-simulation.js', 'snack-chase.js', 'snack-chase.css', 'max-byte-layout-repair.css', 'max-byte-layout-repair.js', 'max-byte-approved-layout.js', 'map-layers.js', 'mission-core.js', 'mission-ui.css', 'shared-map-layout.js', 'map-presentation.js', 'natural-game-core.js', 'customer-game-arena.js', 'offline-route-planner.html', 'offline-route-planner.js', 'offline-routing.js', 'data/gmu_map.json', 'data/mission-route.json', 'data/mission-network.json', 'data/offline-network.json', 'data/natural-game-network.json', 'audio/snack-chase-original-funk.mp3', 'success.html', 'checkout.css', 'login.html', 'customer-account.js', 'verify.html', 'contact.html', 'campusOrderLogs.html', 'site-navigation.css', 'about.html', 'demo-delivery.js']
changes={}
for name in assets:
    path=release/'html/web/public'/name
    if not path.is_file():raise SystemExit('Approved public asset missing: '+name)
    content=path.read_bytes();target='map-data/'+name[5:] if name.startswith('data/') else name
    if name.endswith(('.html','.js','.css')):
        value=content.decode();value=re.sub(r'([\"\'])data/',r'\1map-data/',value)
        if name.endswith('.html'):
            value=re.sub(r'((?:src|href)=[\"\'])([A-Za-z0-9_-]+\.(?:js|css))(?:\?[^\"\']*)?([\"\'])',lambda m:m[1]+m[2]+'?v='+commit[:12]+m[3],value)
        content=value.encode()
    changes[web/target]=content
for path in changes:
    if path.is_symlink() or path.parent.is_symlink() or (path.exists() and not path.is_file()):raise SystemExit('Unexpected public destination: '+str(path))
service=f'''# {managed}
[Unit]
Description=MAX Byte private customer API
After=network.target
[Service]
User=maxbyte-api
Group=maxbyte-api
WorkingDirectory={release}
EnvironmentFile={envfile}
ExecStart={release}/.venv/bin/python -m gunicorn --workers 1 --threads 4 --bind 127.0.0.1:8000 --timeout 45 --access-logfile - --error-logfile - wsgi:app
Restart=on-failure
RestartSec=3
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths={data}
[Install]
WantedBy=multi-user.target
'''.encode()
location=f'''# {managed}
location ^~ /api/ {{
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 45s;
    add_header Cache-Control "no-store" always;
}}
'''.encode()
include='include /etc/nginx/max-byte-api/location.conf;'
newsite=text if include in text else re.sub(r'(?m)^(\s*root\s+/var/www/html\s*;)',lambda m:m[1]+'\n    '+include,text)
configuration={unit:service,proxy:location,site:newsite.encode()}
originals={path:path.read_bytes() if path.exists() else None for path in [*changes,*configuration]}
oldcurrent=os.readlink(current) if current.is_symlink() else None
oldactive=subprocess.run(['systemctl','is-active','--quiet','max-byte-api.service']).returncode==0
oldenabled=subprocess.run(['systemctl','is-enabled','--quiet','max-byte-api.service'],capture_output=True).returncode==0
for path,content in originals.items():
    if content is not None:
        saved=backup/str(path).lstrip('/');saved.parent.mkdir(parents=True,exist_ok=True);saved.write_bytes(content)
(backup/'manifest.json').write_text(json.dumps({'commit':commit,'paths':[str(p) for p in originals],'previous_current':oldcurrent,'previous_api_active':oldactive},indent=2))
written=[]
try:
    for path,content in configuration.items():write_atomic(path,content);written.append(path)
    run(['nginx','-t']);run(['systemctl','daemon-reload']);run(['systemctl','restart','max-byte-api.service'])
    ready=False
    for _ in range(60):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/api/release',timeout=1) as response:body=json.load(response)
            if body.get('commit')==commit and body.get('payments_enabled') is False:ready=True;break
        except Exception:pass
        time.sleep(.25)
    if not ready:raise RuntimeError('Private API did not start with the approved commit; inspect systemctl status max-byte-api.')
    for path,content in sorted(changes.items(),key=lambda pair:pair[0].suffix=='.html'):
        write_atomic(path,content);written.append(path)
    run(['systemctl','reload','nginx'])
    for path,content in changes.items():
        if http(str(path.relative_to(web))+'?verify='+commit[:12])!=content:raise RuntimeError('Public HTTP mismatch: '+str(path))
    # MAX_BYTE_NGINX_READY_WAIT_V33: reload returns before new workers are ready.
    released={};last_error='No API response'
    for attempt in range(40):
        try:
            released=json.loads(http('api/release',timeout=1))
            if released.get('commit')==commit:break
            last_error='Unexpected release ID'
        except (urllib.error.URLError,ValueError,OSError) as error:
            last_error=str(error)
        time.sleep(.25)
    if released.get('commit')!=commit:
        print('API proxy readiness failed: '+last_error,flush=True)
        for line in output(['nginx','-T']).splitlines():
            if any(key in line for key in ('configuration file','listen ','server_name ','max-byte-api','location ^~ /api/')):print(line)
        raise RuntimeError('Public API proxy did not become ready; prior release will be restored.')
    if released.get('commit')!=commit:raise RuntimeError('Nginx API proxy is not serving the approved release.')
    if json.loads(http('api/health')).get('status')!='ok':raise RuntimeError('Live API health failed.')
    catalogue=json.loads(http('api/customer/checkout/catalogue'))
    if catalogue.get('demo_checkout') is not True or catalogue.get('payment_connected') is not False:raise RuntimeError('Expected no-charge public demonstration checkout.')
    if released.get('demonstration_site') is not True or released.get('payments_enabled') is not False:raise RuntimeError('Unexpected public demonstration mode.')
    for private in ['backend/app.py','instance/max_byte.db','data/mission-network.json']:
        try:http(private)
        except urllib.error.HTTPError as error:
            if error.code in (403,404):continue
            raise
        raise RuntimeError('Protected path unexpectedly public: '+private)
    if current.is_symlink():current.unlink()
    current.symlink_to(release,target_is_directory=True)
    run(['systemctl','enable','max-byte-api.service'])
except BaseException:
    for path in reversed(written):
        content=originals[path]
        if content is None:path.unlink(missing_ok=True)
        else:write_atomic(path,content)
    if current.is_symlink():current.unlink()
    if oldcurrent:current.symlink_to(oldcurrent,target_is_directory=True)
    run(['systemctl','daemon-reload'])
    subprocess.run(['systemctl','restart' if oldactive else 'stop','max-byte-api.service'])
    if not oldenabled:subprocess.run(['systemctl','disable','max-byte-api.service'],capture_output=True)
    subprocess.run(['nginx','-t']);subprocess.run(['systemctl','reload','nginx'])
    print('DEPLOYMENT FAILED: API/config/public activation restored. Account database retained; backup: '+str(backup),flush=True)
    raise
(backup/'verified.json').write_text(json.dumps({'commit':commit,'public_http_files':len(changes),'api_verified':True,'payments_enabled':False,'demo_checkout':True,'database':str(dbfile)},indent=2))
print('DEPLOYMENT VERIFIED',flush=True)
print('Commit: '+commit)
print('Public HTTP files verified: '+str(len(changes)))
print('Private Gunicorn API and Nginx proxy verified. Public simulated payment is enabled; actual payments and hardware dispatch remain disabled.')
print('MySQL, port 3000 and existing checkout working directories were not changed.')
print('Private account data persists across future releases. Backup: '+str(backup))
