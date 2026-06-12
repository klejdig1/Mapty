import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
import traceback

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Use in-memory SQLite for Netlify (data resets on each deploy)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'netlify-secret-key-12345')

db = SQLAlchemy(app)

# ==================== MODELS ====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    workouts = db.relationship('Workout', backref='user', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class Workout(db.Model):
    id = db.Column(db.String(10), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    distance = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Float, nullable=False)
    coords = db.Column(db.String(50), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255))
    clicks = db.Column(db.Integer, default=0)
    cadence = db.Column(db.Float)
    pace = db.Column(db.Float)
    elevation_gain = db.Column(db.Float)
    speed = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        coords_list = [float(x) for x in self.coords.split(',')]
        data = {
            'id': self.id,
            'type': self.type,
            'distance': self.distance,
            'duration': self.duration,
            'coords': coords_list,
            'date': self.date.isoformat(),
            'description': self.description,
            'clicks': self.clicks
        }
        if self.type == 'running':
            data['cadence'] = self.cadence
            data['pace'] = self.pace
        elif self.type == 'cycling':
            data['elevationGain'] = self.elevation_gain
            data['speed'] = self.speed
        return data

# ==================== AUTH DECORATOR ====================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return {'message': 'Missing token'}, 401
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return {'message': 'Invalid user'}, 401
        except Exception as e:
            return {'message': 'Invalid token'}, 401
        return f(current_user, *args, **kwargs)
    return decorated

# ==================== ROUTES ====================
@app.route('/api/health', methods=['GET'])
def health():
    return {'status': 'ok'}, 200

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return {'message': 'No data provided'}, 400
            
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return {'message': 'Missing email or password'}, 400
        
        if User.query.filter_by(email=email).first():
            return {'message': 'Email already exists'}, 400
        
        hashed_password = generate_password_hash(password)
        user = User(email=email, password=hashed_password)
        
        db.session.add(user)
        db.session.commit()
        
        token = jwt.encode({'user_id': user.id}, app.config['SECRET_KEY'], algorithm='HS256')
        return {
            'message': 'User registered successfully',
            'token': token,
            'user': user.to_dict()
        }, 201
        
    except Exception as e:
        db.session.rollback()
        return {'message': f'Registration failed: {str(e)}'}, 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return {'message': 'No data provided'}, 400
            
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return {'message': 'Invalid email or password'}, 401
        
        token = jwt.encode({'user_id': user.id}, app.config['SECRET_KEY'], algorithm='HS256')
        return {
            'message': 'Login successful',
            'token': token,
            'user': user.to_dict()
        }, 200
        
    except Exception as e:
        return {'message': f'Login failed: {str(e)}'}, 500

@app.route('/api/workouts', methods=['GET'])
@token_required
def get_workouts(current_user):
    try:
        workouts = Workout.query.filter_by(user_id=current_user.id).all()
        return [w.to_dict() for w in workouts], 200
    except Exception as e:
        return {'message': 'Failed to fetch workouts'}, 500

@app.route('/api/workouts', methods=['POST'])
@token_required
def create_workout(current_user):
    try:
        data = request.get_json()
        if not data:
            return {'message': 'No data provided'}, 400
        
        workout_id = str(int(datetime.utcnow().timestamp() * 1000))[-10:]
        coords_str = f"{data['coords'][0]},{data['coords'][1]}"
        
        workout = Workout(
            id=workout_id,
            user_id=current_user.id,
            type=data['type'],
            distance=data['distance'],
            duration=data['duration'],
            coords=coords_str,
            date=datetime.fromisoformat(data.get('date', datetime.utcnow().isoformat())),
            description=data.get('description'),
            cadence=data.get('cadence'),
            pace=data.get('pace'),
            elevation_gain=data.get('elevationGain'),
            speed=data.get('speed')
        )
        
        db.session.add(workout)
        db.session.commit()
        
        return workout.to_dict(), 201
        
    except Exception as e:
        db.session.rollback()
        return {'message': f'Failed to create workout: {str(e)}'}, 500

@app.route('/api/workouts/<workout_id>', methods=['PUT'])
@token_required
def update_workout(current_user, workout_id):
    try:
        workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
        if not workout:
            return {'message': 'Workout not found'}, 404
        
        data = request.get_json()
        if 'clicks' in data:
            workout.clicks = data['clicks']
        
        db.session.commit()
        return workout.to_dict(), 200
        
    except Exception as e:
        db.session.rollback()
        return {'message': 'Failed to update workout'}, 500

@app.route('/api/workouts/<workout_id>', methods=['DELETE'])
@token_required
def delete_workout(current_user, workout_id):
    try:
        workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
        if not workout:
            return {'message': 'Workout not found'}, 404
        
        db.session.delete(workout)
        db.session.commit()
        return {'message': 'Workout deleted'}, 200
        
    except Exception as e:
        db.session.rollback()
        return {'message': 'Failed to delete workout'}, 500

@app.route('/api/workouts/delete-all', methods=['DELETE'])
@token_required
def delete_all_workouts(current_user):
    try:
        Workout.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return {'message': 'All workouts deleted'}, 200
        
    except Exception as e:
        db.session.rollback()
        return {'message': 'Failed to delete workouts'}, 500

# ==================== NETLIFY HANDLER ====================
def handler(event, context):
    with app.app_context():
        db.create_all()
    
    # Build the WSGI environment
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    headers = event.get('headers', {})
    body = event.get('body', '')
    
    with app.test_request_context(
        path,
        method=http_method,
        headers=headers,
        data=body
    ):
        try:
            rv = app.full_dispatch_request()
            return {
                'statusCode': rv[1] if isinstance(rv, tuple) else 200,
                'body': json.dumps(rv[0]) if isinstance(rv, tuple) else json.dumps(rv),
                'headers': {'Content-Type': 'application/json'}
            }
        except Exception as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'message': str(e)}),
                'headers': {'Content-Type': 'application/json'}
            }
