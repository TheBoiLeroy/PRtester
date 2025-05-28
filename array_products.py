from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from datetime import datetime
import uuid
import os
from werkzeug.security import generate_password_hash, check_password_hash
from typing import List, Dict, Optional

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['S3_BUCKET'] = 'your-s3-bucket'
app.config['S3_REGION'] = 'your-s3-region'
app.config['S3_ACCESS_KEY'] = 'your-access-key'
app.config['S3_SECRET_KEY'] = 'your-secret-key'

CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*')

db = SQLAlchemy(app)

# Models

class User(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        self.password = generate_password_hash(password)

    def check_password(self, password: str):
        return check_password_hash(self.password, password)

class Boss(User):
    __tablename__ = 'bosses'
    org_id = db.Column(db.String(50), nullable=False)
    contractors = db.relationship('Contractor', backref='boss', lazy=True)

class Contractor(User):
    __tablename__ = 'contractors'
    org_id = db.Column(db.String(50), nullable=False)
    boss_id = db.Column(db.Integer, db.ForeignKey('bosses.id'), nullable=True)
    pay_rate = db.Column(db.Float, nullable=True)
    approved = db.Column(db.Boolean, default=False)
    timesheets = db.relationship('Timesheet', backref='contractor', lazy=True)

class Timesheet(db.Model):
    __tablename__ = 'timesheets'
    id = db.Column(db.Integer, primary_key=True)
    contractor_id = db.Column(db.Integer, db.ForeignKey('contractors.id'), nullable=False)
    month = db.Column(db.String(20), nullable=False)
    hours_by_day = db.Column(db.JSON, nullable=False)
    total_pay = db.Column(db.Float, nullable=False)
    image_urls = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Routes

@app.route('/apply', methods=['POST'])
def apply():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    org_id = data.get('org_id')
    password = data.get('password')

    if not all([name, email, org_id, password]):
        return jsonify({'error': 'Missing required fields'}), 400

    # Check if email already exists
    if Contractor.query.filter_by(email=email).first() or Boss.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    # Create contractor
    contractor = Contractor(name=name, email=email, org_id=org_id)
    contractor.set_password(password)
    db.session.add(contractor)
    db.session.commit()

    # Emit event for new contractor application
    socketio.emit('new_contractor', {'contractor_id': contractor.id}, namespace='/')

    return jsonify({'message': 'Contractor applied successfully'}), 201

@app.route('/contractors', methods=['GET'])
def get_contractors():
    # Get current boss from session or token
    boss_id = get_current_boss_id()
    if not boss_id:
        return jsonify({'error': 'Unauthorized'}), 401

    contractors = Contractor.query.filter_by(boss_id=boss_id, approved=True).all()
    return jsonify([{'id': c.id, 'name': c.name, 'email': c.email, 'pay_rate': c.pay_rate} for c in contractors]), 200

@app.route('/approve', methods=['POST'])
def approve_contractor():
    data = request.json
    contractor_id = data.get('contractor_id')
    boss_id = get_current_boss_id()

    if not boss_id:
        return jsonify({'error': 'Unauthorized'}), 401

    contractor = Contractor.query.get(contractor_id)
    if not contractor or contractor.boss_id is not None:
        return jsonify({'error': 'Invalid contractor ID'}), 400

    # Approve contractor and link to boss
    contractor.approved = True
    contractor.boss_id = boss_id
    db.session.commit()

    # Emit event for approval
    socketio.emit('contractor_approved', {'contractor_id': contractor_id}, namespace='/')

    return jsonify({'message': 'Contractor approved successfully'}), 200

@app.route('/timesheets', methods=['POST'])
def submit_timesheet():
    data = request.json
    contractor_id = data.get('contractor_id')
    month = data.get('month')
    hours_by_day = data.get('hours_by_day')
    image_urls = data.get('image_urls', [])

    if not all([contractor_id, month, hours_by_day]):
        return jsonify({'error': 'Missing required fields'}), 400

    contractor = Contractor.query.get(contractor_id)
    if not contractor or contractor.approved is False:
        return jsonify({'error': 'Invalid contractor ID or not approved'}), 400

    total_hours = sum(hours_by_day.values())
    total_pay = total_hours * contractor.pay_rate if contractor.pay_rate else 0

    timesheet = Timesheet(
        contractor_id=contractor_id,
        month=month,
        hours_by_day=hours_by_day,
        total_pay=total_pay,
        image_urls=image_urls
    )
    db.session.add(timesheet)
    db.session.commit()

    # Emit event for timesheet submission
    socketio.emit('timesheet_submitted', {'contractor_id': contractor_id, 'month': month}, namespace='/')

    return jsonify({'message': 'Timesheet submitted successfully'}), 201

@app.route('/timesheets', methods=['GET'])
def get_timesheets():
    boss_id = get_current_boss_id()
    if not boss_id:
        return jsonify({'error': 'Unauthorized'}), 401

    timesheets = Timesheet.query.filter_by(boss_id=boss_id).all()
    return jsonify([{
        'contractor_id': t.contractor_id,
        'month': t.month,
        'total_hours': sum(t.hours_by_day.values()),
        'total_pay': t.total_pay,
        'image_urls': t.image_urls
    } for t in timesheets]), 200

# Helper functions

def get_current_boss_id():
    # In a real app, this would retrieve the boss ID from a session or token
    # For simplicity, we'll assume it's passed in the request headers
    return request.headers.get('boss_id')

# SocketIO events

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
