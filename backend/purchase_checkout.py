"""Purchase-scoped checkout and reward ledger; all prices computed by server.
Local demonstration checkout is enabled only by the localhost preview runner.
Production payment confirmation must come from a verified payment adapter.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
import secrets
import time
import uuid
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from backend.app import db
from backend.customer_routes import CustomerMission, RouteInputError, protect_write, bad_input

class DeliveryPurchase(db.Model):
    __tablename__='delivery_purchases'
    id=db.Column(db.String(36),primary_key=True)
    owner_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    mission_id=db.Column(db.String(36),db.ForeignKey('customer_route_missions.id'),nullable=False,unique=True)
    request_key=db.Column(db.String(80),nullable=False)
    fingerprint=db.Column(db.Text,nullable=False)
    status=db.Column(db.String(24),nullable=False)
    line_items=db.Column(db.Text,nullable=False)
    subtotal_cents=db.Column(db.Integer,nullable=False)
    discount_cents=db.Column(db.Integer,nullable=False)
    delivery_cents=db.Column(db.Integer,nullable=False)
    total_cents=db.Column(db.Integer,nullable=False)
    created_at=db.Column(db.Float,nullable=False)
    payment_reference=db.Column(db.String(120),unique=True,nullable=True)
    __table_args__=(db.UniqueConstraint('owner_id','request_key',name='uq_purchase_request'),)

class PurchaseCoupon(db.Model):
    __tablename__='purchase_snack_coupons'
    id=db.Column(db.String(36),primary_key=True)
    owner_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    purchase_id=db.Column(db.String(36),db.ForeignKey('delivery_purchases.id'),nullable=False,unique=True)
    run_id=db.Column(db.String(36),db.ForeignKey('snack_runs.id'),nullable=False,unique=True)
    code=db.Column(db.String(40),nullable=False,unique=True)
    issued_at=db.Column(db.Float,nullable=False)
    expires_at=db.Column(db.Float,nullable=False)
    redeemed_order_id=db.Column(db.String(36),db.ForeignKey('delivery_purchases.id'),nullable=True,unique=True)

bp=Blueprint('purchase_checkout',__name__,url_prefix='/api/customer')
bp.before_request(protect_write);bp.register_error_handler(RouteInputError,bad_input)

def clock():return current_app.config.get('SNACK_CLOCK',time.time)()
def fail(code,message,status=400):raise RouteInputError(code,message,status)
def catalogue():return current_app.config['MAX_BYTE_CATALOGUE']
def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict):fail('invalid_request','Use a JSON checkout request.')
    return data

def price(data):
    identity=data.get('mission_id')
    if not isinstance(identity,str) or len(identity)!=36:fail('mission_required','Choose a saved delivery location.')
    mission=CustomerMission.query.filter_by(id=identity,owner_id=current_user.id).first()
    if not mission:fail('mission_required','Choose one of your saved delivery locations.',404)
    items=data.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=30:fail('items_required','Choose 1 to 30 menu items.')
    lines=[];seen=set();subtotal=0
    for item in items:
        if not isinstance(item,dict):fail('invalid_item','Invalid menu item.')
        sku=item.get('sku');quantity=item.get('quantity')
        if not isinstance(sku,str) or sku not in catalogue() or sku in seen:fail('invalid_item','Unknown or repeated menu item.')
        if type(quantity) is not int or not 1<=quantity<=20:fail('invalid_quantity','Quantity must be 1 to 20.')
        seen.add(sku);product=catalogue()[sku];line=quantity*product['price_cents'];subtotal+=line
        lines.append({'sku':sku,'name':product['name'],'quantity':quantity,'unit_cents':product['price_cents'],'line_cents':line})
    coupon=None;code=data.get('coupon_code','')
    if not isinstance(code,str) or len(code)>40:fail('invalid_coupon','Invalid coupon.')
    code=code.strip().upper()
    if code:
        coupon=PurchaseCoupon.query.filter_by(code=code,owner_id=current_user.id).first()
        if not coupon:fail('invalid_coupon','Coupon not found in your account.',422)
        if coupon.redeemed_order_id:fail('coupon_used','This coupon has already been used.',409)
        if clock()>=coupon.expires_at:fail('coupon_expired','This coupon has expired.',422)
        origin=db.session.get(DeliveryPurchase,coupon.purchase_id)
        if not origin or origin.status not in {'paid','demo_confirmed'}:fail('invalid_coupon','Coupon is not eligible.',422)
        if origin.status=='demo_confirmed' and not current_app.config.get('ALLOW_DEMO_CHECKOUT',False):fail('demo_coupon','Demonstration coupons cannot discount real purchases.',422)
    discount=int((Decimal(subtotal)*Decimal('0.15')).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if coupon else 0
    delivery=current_app.config.get('MAX_BYTE_DELIVERY_CENTS',199)
    return mission,lines,coupon,{'subtotal_cents':subtotal,'discount_cents':discount,'delivery_cents':delivery,'total_cents':subtotal-discount+delivery,'currency':'USD','discount_scope':'food subtotal; delivery excluded'}

def eligible_purchase(mission_id,owner_id):
    row=DeliveryPurchase.query.filter_by(mission_id=mission_id,owner_id=owner_id).first()
    if not row:fail('purchase_required','Complete checkout for this delivery before playing for a coupon.',409)
    if row.status!='paid' and not (row.status=='demo_confirmed' and current_app.config.get('ALLOW_DEMO_CHECKOUT',False)):
        fail('purchase_required','A confirmed delivery purchase is required.',409)
    return row

def purchase_json(p):
    return {'purchase_id':p.id,'mission_id':p.mission_id,'status':p.status,'items':json.loads(p.line_items),'subtotal_cents':p.subtotal_cents,'discount_cents':p.discount_cents,'delivery_cents':p.delivery_cents,'total_cents':p.total_cents,'currency':'USD','map_url':'MapAPI.html?mission='+p.mission_id,'game_attempts':1}

@bp.get('/checkout/catalogue')
def menu_catalogue():
    return jsonify(items=[dict(sku=k,**v) for k,v in catalogue().items()],demo_checkout=bool(current_app.config.get('ALLOW_DEMO_CHECKOUT',False)),delivery_cents=current_app.config.get('MAX_BYTE_DELIVERY_CENTS',199),payment_connected=False)

@bp.post('/checkout/quote')
@login_required
def quote():
    _,lines,_,totals=price(body());return jsonify(**totals,items=lines,demo_checkout=bool(current_app.config.get('ALLOW_DEMO_CHECKOUT',False)))

@bp.post('/checkout/complete')
@login_required
def complete():
    # Never trust a client 'paid' flag or invent a payment confirmation.
    if not current_app.config.get('ALLOW_DEMO_CHECKOUT',False):fail('payment_not_connected','Payment processing is not connected. No purchase or coupon redemption was recorded.',503)
    data=body();key=request.headers.get('Idempotency-Key','')
    if not 8<=len(key)<=80 or not all(c.isalnum() or c in '-_' for c in key):fail('request_key_required','A valid checkout request key is required.')
    fingerprint=json.dumps({k:data.get(k) for k in ['mission_id','items','coupon_code']},sort_keys=True)
    existing=DeliveryPurchase.query.filter_by(owner_id=current_user.id,request_key=key).first()
    if existing:
        if existing.fingerprint!=fingerprint:fail('request_key_conflict','This checkout key belongs to another purchase.',409)
        return jsonify(**purchase_json(existing),replayed=True)
    mission,lines,coupon,totals=price(data);timestamp=clock();identity=str(uuid.uuid4());mission_id=str(uuid.uuid4())
    # Every purchase gets a separate mission and therefore exactly one run.
    copied=CustomerMission(id=mission_id,owner_id=current_user.id,request_key='purchase-'+identity,reference='Purchase '+identity,payload=mission.payload)
    purchase=DeliveryPurchase(id=identity,owner_id=current_user.id,mission_id=mission_id,request_key=key,fingerprint=fingerprint,status='demo_confirmed',line_items=json.dumps(lines),created_at=timestamp,**{k:totals[k] for k in ['subtotal_cents','discount_cents','delivery_cents','total_cents']})
    try:
        db.session.add(copied);db.session.flush();db.session.add(purchase);db.session.flush()
        if coupon:
            # Conditional database update makes concurrent/replayed redemption one-use.
            changed=PurchaseCoupon.query.filter_by(id=coupon.id,owner_id=current_user.id,redeemed_order_id=None).filter(PurchaseCoupon.expires_at>timestamp).update({'redeemed_order_id':identity},synchronize_session=False)
            if changed!=1:db.session.rollback();fail('coupon_used','Coupon is no longer available.',409)
        db.session.commit()
    except IntegrityError:
        db.session.rollback();fail('checkout_retry','Checkout request conflicted. Retry with the same key.',409)
    return jsonify(**purchase_json(purchase),replayed=False,notice='Local demonstration purchase only. No money was charged and no food dispatched.'),201

@bp.get('/purchases')
@login_required
def purchases():
    rows=DeliveryPurchase.query.filter_by(owner_id=current_user.id).order_by(DeliveryPurchase.created_at.desc()).limit(50).all()
    return jsonify(purchases=[purchase_json(p) for p in rows])

def register_checkout(app,limiter):
    from pathlib import Path
    app.config.setdefault('MAX_BYTE_CATALOGUE',json.loads((Path(__file__).parent/'menu_catalogue.json').read_text()))
    app.register_blueprint(bp)
    for endpoint in ['purchase_checkout.quote','purchase_checkout.complete']:
        handler=app.view_functions[endpoint]
        def invoke(*args,_handler=handler,**kwargs):return _handler(*args,**kwargs)
        invoke.__name__=endpoint.replace('.','_');app.view_functions[endpoint]=limiter.limit('20 per minute')(invoke)
