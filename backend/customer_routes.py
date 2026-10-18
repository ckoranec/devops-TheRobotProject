"""Authenticated mission storage around the team's existing simulated Dijkstra.
No hardware dispatch, shared map writes, geocoding calls or coupon issuance.
"""
from datetime import datetime, timezone
from pathlib import Path
import hmac
import json
import secrets
import uuid
from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from backend.app import db
from backend.map_route_service import make_mission, PICKUP, DESTINATION, valid_point

class CustomerMission(db.Model):
    __tablename__ = 'customer_route_missions'
    id = db.Column(db.String(36), primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    request_key = db.Column(db.String(80), nullable=False)
    reference = db.Column(db.String(80), nullable=False, default='')
    payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('owner_id', 'request_key', name='uq_customer_mission_request'),)

bp = Blueprint('customer_routes', __name__, url_prefix='/api/customer')

class RouteInputError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status

@bp.errorhandler(RouteInputError)
def bad_input(error):
    return jsonify(error=error.message, code=error.code), error.status

@bp.errorhandler(429)
def too_many_requests(error):
    return jsonify(error='Too many routing requests. Wait a minute and try again.', code='rate_limited'), 429

@bp.before_request
def protect_write():
    # Reject cross-origin mutations and require a session-bound CSRF token.
    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return
    origin = request.headers.get('Origin')
    if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
        raise RouteInputError('origin_rejected', 'Use this website to submit the request.', 403)
    supplied = request.headers.get('X-CSRF-Token', '')
    expected = session.get('customer_route_csrf', '')
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise RouteInputError('csrf_required', 'Refresh the session and try again.', 403)

@bp.get('/session')
def customer_session():
    if 'customer_route_csrf' not in session:
        session['customer_route_csrf'] = secrets.token_urlsafe(32)
    return jsonify(csrf_token=session['customer_route_csrf'], authenticated=current_user.is_authenticated,
                   email=current_user.email if current_user.is_authenticated else None)

@bp.get('/destinations')
def destinations():
    # Known address catalogue only. Unlisted addresses are not silently geocoded.
    return jsonify(pickup={'name':'Horizon Hall, 4475 Aquia Creek Lane', 'lat':PICKUP[0], 'lon':PICKUP[1]},
        destinations=[{'id':'overcup-4504', 'name':'4504 Overcup Court', 'lat':DESTINATION[0], 'lon':DESTINATION[1]}],
        simulated=True, address_search='Known address or manually confirmed map point; free-text geocoding pending')

def input_data():
    if not request.is_json:
        raise RouteInputError('json_required', 'A JSON request is required.', 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise RouteInputError('invalid_request', 'Request must be a JSON object.')
    point = data.get('destination')
    if not isinstance(point, dict):
        raise RouteInputError('destination_required', 'Select a destination on the map.')
    coordinates = (point.get('lat'), point.get('lon'))
    if not valid_point(coordinates):
        raise RouteInputError('invalid_coordinates', 'Use valid numeric latitude and longitude.')
    name = data.get('destination_name', 'Selected map destination')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise RouteInputError('invalid_label', 'Destination label must contain 1 to 200 characters.')
    return data, coordinates, name.strip()

def calculate(coordinates, name):
    source = Path(current_app.config.get('CUSTOMER_MAP_SOURCE', Path(current_app.root_path).parent/'gmu_map_16OCT26.json'))
    if not source.is_file():
        raise RouteInputError('map_unavailable', 'Routing data is unavailable. Try again later.', 503)
    try:
        mission, _, _ = make_mission(source, destination=coordinates)
    except (OSError, json.JSONDecodeError):
        raise RouteInputError('map_unavailable', 'Routing data could not be read. Try again later.', 503)
    except ValueError as exc:
        message = str(exc)
        if 'Endpoint is' in message:
            raise RouteInputError('excessive_snap', 'The destination is more than 35 metres from an eligible mapped path. Choose a nearby accessible point.', 422)
        if 'same node' in message:
            raise RouteInputError('same_endpoint', 'Choose a destination different from Horizon Hall.', 422)
        if 'No connected' in message:
            raise RouteInputError('disconnected_route', 'No connected outbound and return route exists. Choose another destination.', 422)
        current_app.logger.warning('Routing source validation failed: %s', message)
        raise RouteInputError('map_invalid', 'Routing data failed validation. No route was saved.', 503)
    mission['metadata']['destination_name'] = name
    mission['metadata']['simulation_speed_mph'] = 15
    mission['metadata']['delivery_eta_seconds'] = mission['metadata']['outbound_m']/(15*.44704)
    mission['metadata']['return_eta_seconds'] = mission['metadata']['total_m']/(15*.44704)
    return mission

@bp.post('/routes/preview')
def preview_route():
    _, coordinates, name = input_data()
    return jsonify(calculate(coordinates, name))

@bp.post('/missions')
@login_required
def create_mission():
    data, coordinates, name = input_data()
    if data.get('confirmed') is not True:
        raise RouteInputError('confirmation_required', 'Confirm the destination pin before saving.')
    key = request.headers.get('Idempotency-Key', '')
    if not 8 <= len(key) <= 80 or not all(c.isalnum() or c in '-_' for c in key):
        raise RouteInputError('request_key_required', 'A valid request key is required.')
    reference = data.get('reference', '')
    if not isinstance(reference, str) or len(reference) > 80:
        raise RouteInputError('invalid_reference', 'Reference must contain no more than 80 characters.')
    existing = CustomerMission.query.filter_by(owner_id=current_user.id, request_key=key).first()
    if existing:
        old = json.loads(existing.payload)['metadata']
        if old['destination'] != list(coordinates) or old['destination_name'] != name or existing.reference != reference:
            raise RouteInputError('request_key_conflict', 'This request key was already used for another destination.', 409)
        return jsonify(mission_id=existing.id, mission=json.loads(existing.payload), replayed=True), 200
    mission = calculate(coordinates, name)
    row = CustomerMission(id=str(uuid.uuid4()), owner_id=current_user.id, request_key=key,
                          reference=reference, payload=json.dumps(mission, allow_nan=False))
    try:
        db.session.add(row)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise RouteInputError('request_in_progress', 'This request is already being saved. Retry with the same request key.', 409)
    except SQLAlchemyError:
        db.session.rollback()
        raise RouteInputError('storage_unavailable', 'The mission could not be saved. Try again later.', 503)
    return jsonify(mission_id=row.id, mission=mission, replayed=False), 201

@bp.get('/missions/<mission_id>')
@login_required
def read_mission(mission_id):
    row = CustomerMission.query.filter_by(id=mission_id, owner_id=current_user.id).first()
    if not row:
        raise RouteInputError('not_found', 'Mission not found.', 404)
    return jsonify(mission_id=row.id, reference=row.reference, mission=json.loads(row.payload))

@bp.get('/missions')
@login_required
def list_missions():
    rows = CustomerMission.query.filter_by(owner_id=current_user.id).order_by(CustomerMission.created_at.desc()).limit(50).all()
    return jsonify(missions=[{'mission_id':r.id, 'reference':r.reference,
                   'destination_name':json.loads(r.payload)['metadata']['destination_name'],
                   'created_at':r.created_at.isoformat()} for r in rows])

def register_customer_routes(app, limiter):
    # Limits use the application's existing limiter; no extra dependency.
    # Keep a strong reference even when rate limiting is disabled in tests.
    app.extensions['customer_route_limiter'] = limiter
    app.register_blueprint(bp)
    for endpoint in ['customer_routes.preview_route', 'customer_routes.create_mission']:
        handler = app.view_functions[endpoint]
        def invoke(*args, _handler=handler, **kwargs):
            return _handler(*args, **kwargs)
        invoke.__name__ = endpoint.replace('.', '_')
        app.view_functions[endpoint] = limiter.limit('10 per minute')(invoke)
