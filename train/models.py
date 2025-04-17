from train import db
# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# Booking model
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    train_no = db.Column(db.String(20), nullable=False)
    train_name = db.Column(db.String(100), nullable=False)
    from_station = db.Column(db.String(100), nullable=False)
    to_station = db.Column(db.String(100), nullable=False)
    journey_date = db.Column(db.String(20), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    total_fare = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    passengers = db.Column(db.Text, nullable=False)  # Store passenger details as JSON string
