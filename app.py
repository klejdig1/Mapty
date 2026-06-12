from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import jwt
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mapty.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

db = SQLAlchemy(app)

# Models
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
    type = db.Column(db.String(20), nullable=False)  # 'running' or 'cycling'
    distance = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Float, nullable=False)  # minutes
    coords = db.Column(db.String(50), nullable=False)  # "lat,lng"
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(255))
    clicks = db.Column(db.Integer, default=0)
    
    # Running specific
    cadence = db.Column(db.Float)
    pace = db.Column(db.Float)
    
    # Cycling specific
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

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Missing token'}), 401
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'message': 'Invalid user'}), 401
        except:
            return jsonify({'message': 'Invalid token'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Routes
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'message': 'Missing email or password'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists'}), 400
    
    from werkzeug.security import generate_password_hash
    user = User(email=email, password=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    
    token = jwt.encode({'user_id': user.id}, app.config['SECRET_KEY'], algorithm='HS256')
    return jsonify({
        'message': 'User registered',
        'token': token,
        'user': user.to_dict()
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Invalid email or password'}), 401
    
    from werkzeug.security import check_password_hash
    if not check_password_hash(user.password, password):
        return jsonify({'message': 'Invalid email or password'}), 401
    
    token = jwt.encode({'user_id': user.id}, app.config['SECRET_KEY'], algorithm='HS256')
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    }), 200

@app.route('/api/workouts', methods=['GET'])
@token_required
def get_workouts(current_user):
    workouts = Workout.query.filter_by(user_id=current_user.id).all()
    return jsonify([w.to_dict() for w in workouts]), 200

@app.route('/api/workouts', methods=['POST'])
@token_required
def create_workout(current_user):
    data = request.get_json()
    
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
    
    return jsonify(workout.to_dict()), 201

@app.route('/api/workouts/<workout_id>', methods=['PUT'])
@token_required
def update_workout(current_user, workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
    if not workout:
        return jsonify({'message': 'Workout not found'}), 404
    
    data = request.get_json()
    if 'clicks' in data:
        workout.clicks = data['clicks']
    
    db.session.commit()
    return jsonify(workout.to_dict()), 200

@app.route('/api/workouts/<workout_id>', methods=['DELETE'])
@token_required
def delete_workout(current_user, workout_id):
    workout = Workout.query.filter_by(id=workout_id, user_id=current_user.id).first()
    if not workout:
        return jsonify({'message': 'Workout not found'}), 404
    
    db.session.delete(workout)
    db.session.commit()
    
    return jsonify({'message': 'Workout deleted'}), 200

@app.route('/api/workouts/delete-all', methods=['DELETE'])
@token_required
def delete_all_workouts(current_user):
    Workout.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'message': 'All workouts deleted'}), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)