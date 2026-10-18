"""Serve the existing project website and API together on localhost:8000.
Stop python -m http.server 8000 first; this runner replaces that process only.
"""
from pathlib import Path
from datetime import datetime
import os,secrets,sqlite3,socket
from flask import send_from_directory,abort
from backend.app import create_app
root=Path(__file__).resolve().parent

def make_local_app():
    private=root/'instance';private.mkdir(exist_ok=True)
    secret=private/'customer-local-secret.txt'
    if not secret.exists():
        secret.write_text(secrets.token_hex(32));secret.chmod(0o600)
    # Back up the existing SQLite database before adding the mission table.
    database=private/'max_byte.db'
    if database.exists():
        folder=root/'customer-routing-db-backups';folder.mkdir(exist_ok=True)
        target=folder/('max_byte-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
        with sqlite3.connect(database) as source,sqlite3.connect(target) as saved:source.backup(saved)
        print('Database backup:',target)
    app=create_app({'SECRET_KEY':os.environ.get('MAX_BYTE_SECRET_KEY') or secret.read_text().strip(),
                    'SQLALCHEMY_DATABASE_URI':'sqlite:///'+database.as_posix(),
                    'CUSTOMER_MAP_SOURCE':str(root/'gmu_map_16OCT26.json'),
                    # Local-only checkout tests never charge or dispatch.
                    'ALLOW_DEMO_CHECKOUT':True})
    allowed={'.css','.png','.jpg','.jpeg','.svg','.webp','.gif','.woff','.woff2','.ttf','.json','.mp3','.wav','.ogg','.ico'}
    def asset(directory,filename):
        parts=filename.replace(chr(92),'/').split('/')
        if any(p.startswith('.') or 'backup' in p.lower() or '.before-' in p.lower() for p in parts) or Path(filename).suffix.lower() not in allowed:abort(404)
        return send_from_directory(directory,filename)
    @app.get('/css/<path:filename>')
    def local_css(filename):
        public=root/'html/web/public/css'
        directory=public if (public/filename).is_file() else root/'html/web/css'
        return asset(directory,filename)
    @app.get('/data/<path:filename>')
    def local_data(filename):
        public=root/'html/web/public/data'
        directory=public if (public/filename).is_file() else root/'html/data'
        return asset(directory,filename)
    return app

if __name__=='__main__':
    # Detect a busy port before opening the database or starting Flask.
    with socket.socket() as check:
        try:check.bind(('127.0.0.1',8000))
        except OSError:raise SystemExit('Port 8000 is busy. Stop the existing HTTP server with Ctrl+C, then run this command again.')
    app=make_local_app()
    print('Same project, website, account database and port 8000.')
    print('Existing maps: http://127.0.0.1:8000/MapAPI.html')
    print('Delivery location: http://127.0.0.1:8000/delivery-location.html')
    app.run(host='127.0.0.1',port=8000,debug=False)
