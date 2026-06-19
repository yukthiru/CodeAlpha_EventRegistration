from flask import Flask, request, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    capacity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    registrations = db.relationship('Registration', backref='event', lazy=True, cascade="all, delete-orphan")

    def to_dict(self, include_count=False):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "date": self.date,
            "location": self.location,
            "capacity": self.capacity,
            "created_at": self.created_at.isoformat()
        }
        if include_count:
            active = Registration.query.filter_by(event_id=self.id, status='confirmed').count()
            data["registered_count"] = active
            data["spots_left"] = max(self.capacity - active, 0) if self.capacity else None
        return data


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), default='confirmed')  # confirmed / cancelled
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_title": self.event.title if self.event else None,
            "name": self.name,
            "email": self.email,
            "status": self.status,
            "registered_at": self.registered_at.isoformat()
        }


# ---------------- Page routes ----------------

@app.route('/')
def index():
    return render_template('index.html')


# ---------------- Event APIs ----------------

@app.route('/api/events', methods=['GET'])
def list_events():
    events = Event.query.order_by(Event.date.asc()).all()
    return jsonify([e.to_dict(include_count=True) for e in events])


@app.route('/api/events', methods=['POST'])
def create_event():
    data = request.get_json() if request.is_json else request.form

    title = data.get('title', '').strip()
    date = data.get('date', '').strip()
    location = data.get('location', '').strip()
    description = data.get('description', '').strip()
    capacity = data.get('capacity', 0)

    if not title or not date or not location:
        return jsonify({"error": "title, date and location are required"}), 400

    try:
        capacity = int(capacity) if capacity else 0
    except ValueError:
        capacity = 0

    event = Event(title=title, description=description, date=date, location=location, capacity=capacity)
    db.session.add(event)
    db.session.commit()

    return jsonify(event.to_dict(include_count=True)), 201


@app.route('/api/events/<int:event_id>', methods=['GET'])
def get_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    return jsonify(event.to_dict(include_count=True))


@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    db.session.delete(event)
    db.session.commit()
    return jsonify({"message": "Event deleted"}), 200


# ---------------- Registration APIs ----------------

@app.route('/api/events/<int:event_id>/register', methods=['POST'])
def register_for_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404

    data = request.get_json() if request.is_json else request.form
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()

    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400

    existing = Registration.query.filter_by(event_id=event_id, email=email, status='confirmed').first()
    if existing:
        return jsonify({"error": "You are already registered for this event"}), 400

    if event.capacity:
        active_count = Registration.query.filter_by(event_id=event_id, status='confirmed').count()
        if active_count >= event.capacity:
            return jsonify({"error": "Event is fully booked"}), 400

    registration = Registration(event_id=event_id, name=name, email=email, status='confirmed')
    db.session.add(registration)
    db.session.commit()

    return jsonify(registration.to_dict()), 201


@app.route('/api/registrations', methods=['GET'])
def list_registrations():
    email = request.args.get('email', '').strip()
    query = Registration.query
    if email:
        query = query.filter_by(email=email)
    registrations = query.order_by(Registration.registered_at.desc()).all()
    return jsonify([r.to_dict() for r in registrations])


@app.route('/api/registrations/<int:registration_id>/cancel', methods=['POST'])
def cancel_registration(registration_id):
    registration = Registration.query.get(registration_id)
    if not registration:
        return jsonify({"error": "Registration not found"}), 404

    registration.status = 'cancelled'
    db.session.commit()

    return jsonify(registration.to_dict()), 200


@app.route('/api/registrations/<int:registration_id>', methods=['DELETE'])
def delete_registration(registration_id):
    registration = Registration.query.get(registration_id)
    if not registration:
        return jsonify({"error": "Registration not found"}), 404

    db.session.delete(registration)
    db.session.commit()

    return jsonify({"message": "Registration deleted"}), 200


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)