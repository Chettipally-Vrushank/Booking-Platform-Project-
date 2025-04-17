from flask import redirect,render_template,url_for,flash,request,session,jsonify
from train import db,app,bcrypt
from train.models import User, Booking
import sqlite3
import os
from PIL import Image
import io
import json

# Routes
@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session["user_id"] = user.id
            session["user_name"] = user.name
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
        else:
            new_user = User(name=name, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect("trains.db")
    cursor = conn.cursor()

    # Get unique station names from the database
    cursor.execute("SELECT DISTINCT Station_Name FROM train_schedule")
    stations = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template("dashboard.html", name=session["user_name"], stations=stations)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/about")
def about():
    return render_template("about.html")



@app.route('/carousel')
def carousel_page():
    return render_template('carousel.html')

@app.route("/results", methods=["GET"])
def results():
    from_station = request.args.get("from")
    to_station = request.args.get("to")
    date = request.args.get("date")

    conn = sqlite3.connect("trains.db")
    cursor = conn.cursor()

    # Query trains between selected stations
    query = """
        SELECT Train_No, Train_Name, Arrival_Time, Departure_Time, Distance, General_Fare, Sleeper_Fare, AC_Fare
        FROM train_schedule
        WHERE Station_Name = ? AND Destination_Station_Name = ?
    """
    cursor.execute(query, (from_station, to_station))
    trains = cursor.fetchall()
    
    conn.close()

    return render_template("results.html", trains=trains, from_station=from_station, to_station=to_station, date=date)



@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        # Get payment details
        name = request.form.get('name')
        cvv = request.form.get('cvv')
        card_number = request.form.get('card_number')
        expiry_date = request.form.get('expiry_date')
        
        # Get passenger and journey details from session
        passengers = session.get('passengers', [])
        train_no = session.get('train_no')
        train_name = session.get('train_name')
        from_station = session.get('from_station')
        to_station = session.get('to_station')
        date = session.get('date')
        
        # Get fare information from the database
        conn = sqlite3.connect("trains.db")
        cursor = conn.cursor()
        query = """
            SELECT General_Fare, Sleeper_Fare, AC_Fare
            FROM train_schedule
            WHERE Train_No = ? AND Station_Name = ? AND Destination_Station_Name = ?
        """
        cursor.execute(query, (train_no, from_station, to_station))
        fares = cursor.fetchone()
        conn.close()
        
        if fares:
            general_fare, sleeper_fare, ac_fare = fares
            
            # Calculate fare for each passenger and update the passenger data
            total_fare = 0
            for passenger in passengers:
                if passenger['class'] == 'general':
                    passenger['fare'] = general_fare
                elif passenger['class'] == 'sleeper':
                    passenger['fare'] = sleeper_fare
                else:  # AC class
                    passenger['fare'] = ac_fare
                total_fare += passenger['fare']
            
            # Update the passengers in session with fare information
            session['passengers'] = passengers
            
            # Create a new booking record
            new_booking = Booking(
                user_id=session['user_id'],
                train_no=train_no,
                train_name=train_name,
                from_station=from_station,
                to_station=to_station,
                journey_date=date,
                total_fare=total_fare,
                passengers=json.dumps(passengers)
            )
            
            # Add the booking to the database
            db.session.add(new_booking)
            db.session.commit()
        
        # Store payment details in session
        session['payment_details'] = {
            'name': name,
            'card_number': card_number[-4:],  # Store only last 4 digits
            'expiry_date': expiry_date
        }
        
        # Redirect to ticket details page
        return redirect(url_for('ticket_details'))
    
    return render_template('payment.html')

@app.route('/ticket_details')
def ticket_details():
    # Get all details from session
    passengers = session.get('passengers', [])
    train_no = session.get('train_no')
    train_name = session.get('train_name')
    from_station = session.get('from_station')
    to_station = session.get('to_station')
    date = session.get('date')
    payment_details = session.get('payment_details', {})
    
    # Calculate total fare
    total_fare = sum(passenger.get('fare', 0) for passenger in passengers)
    
    # Check if all required data is present
    if not all([passengers, train_no, train_name, from_station, to_station, date]):
        flash("Error: Missing booking information. Please try again.", "danger")
        return redirect(url_for('home'))
    
    return render_template('ticket_details.html',
                         passengers=passengers,
                         train_no=train_no,
                         train_name=train_name,
                         from_station=from_station,
                         to_station=to_station,
                         date=date,
                         payment_details=payment_details,
                         total_fare=total_fare)

@app.route("/add_passengers", methods=["GET", "POST"])
def add_passengers():
    if request.method == "GET":
        train_no = request.args.get("train_no")
        train_name = request.args.get("train_name")
        from_station = request.args.get("from_station")
        to_station = request.args.get("to_station")
        date = request.args.get("date")

        # Get fare information from the database
        conn = sqlite3.connect("trains.db")
        cursor = conn.cursor()
        query = """
            SELECT General_Fare, Sleeper_Fare, AC_Fare
            FROM train_schedule
            WHERE Train_No = ? AND Station_Name = ? AND Destination_Station_Name = ?
        """
        cursor.execute(query, (train_no, from_station, to_station))
        fares = cursor.fetchone()
        conn.close()

        if fares:
            general_fare, sleeper_fare, ac_fare = fares
        else:
            flash("Train information not found.", "danger")
            return redirect(url_for("dashboard"))

        return render_template("add_passengers.html",
                             train_no=train_no,
                             train_name=train_name,
                             from_station=from_station,
                             to_station=to_station,
                             date=date,
                             general_fare=general_fare,
                             sleeper_fare=sleeper_fare,
                             ac_fare=ac_fare,
                             total_fare=0)

    elif request.method == "POST":
        # Get the number of passengers
        num_passengers = int(request.form.get("num_passengers"))
        passengers = []

        # Get fare information from the database
        train_no = request.form.get("train_no")
        from_station = request.form.get("from_station")
        to_station = request.form.get("to_station")
        
        conn = sqlite3.connect("trains.db")
        cursor = conn.cursor()
        query = """
            SELECT General_Fare, Sleeper_Fare, AC_Fare
            FROM train_schedule
            WHERE Train_No = ? AND Station_Name = ? AND Destination_Station_Name = ?
        """
        cursor.execute(query, (train_no, from_station, to_station))
        fares = cursor.fetchone()
        conn.close()

        if fares:
            general_fare, sleeper_fare, ac_fare = fares
        else:
            flash("Train information not found.", "danger")
            return redirect(url_for("dashboard"))

        # Collect passenger details and calculate fare
        for i in range(1, num_passengers + 1):
            passenger_class = request.form.get(f"passenger_{i}_class")
            fare = 0
            if passenger_class == 'general':
                fare = general_fare
            elif passenger_class == 'sleeper':
                fare = sleeper_fare
            else:  # AC class
                fare = ac_fare

            passenger = {
                "name": request.form.get(f"passenger_{i}_name"),
                "age": request.form.get(f"passenger_{i}_age"),
                "gender": request.form.get(f"passenger_{i}_gender"),
                "phone": request.form.get(f"passenger_{i}_phone"),
                "class": passenger_class,
                "fare": fare
            }
            passengers.append(passenger)

        # Store passenger details in session for payment page
        session["passengers"] = passengers
        session["train_no"] = train_no
        session["train_name"] = request.form.get("train_name")
        session["from_station"] = from_station
        session["to_station"] = to_station
        session["date"] = request.form.get("date")

        return redirect(url_for("payment"))

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get user's bookings using SQLAlchemy
    user_bookings = Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.booking_date.desc()).all()
    
    bookings = []
    # Enumerate through bookings to add a sequential booking number for this user
    for index, booking in enumerate(user_bookings, start=1):
        bookings.append({
            'booking_number': index,  # Sequential number for this user's bookings
            'id': booking.id,
            'train_no': booking.train_no,
            'train_name': booking.train_name,
            'from_station': booking.from_station,
            'to_station': booking.to_station,
            'journey_date': booking.journey_date,
            'total_fare': booking.total_fare,
            'booking_date': booking.booking_date,
            'passengers': booking.passengers
        })
    
    # Check if user has a profile picture
    profile_pic = f"{session['user_id']}_profile.jpg"
    profile_pic_path = os.path.join(app.static_folder, 'profile-pics', profile_pic)
    
    if not os.path.exists(profile_pic_path):
        profile_pic = None
    
    return render_template('profile.html', 
                         bookings=bookings, 
                         profile_pic=profile_pic,
                         timestamp=int(os.path.getmtime(profile_pic_path)) if profile_pic else '')

@app.route('/upload_profile_pic', methods=['POST'])
def upload_profile_pic():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    try:
        # Create profile-pics directory if it doesn't exist
        profile_pics_dir = os.path.join(app.static_folder, 'profile-pics')
        os.makedirs(profile_pics_dir, exist_ok=True)
        
        print("Request files:", request.files)  # Debug log
        
        if 'file' not in request.files:
            print("No file in request.files")  # Debug log
            return jsonify({'success': False, 'message': 'No file uploaded'})
            
        file = request.files['file']
        print("File name:", file.filename)  # Debug log
        
        if file.filename == '':
            print("Empty filename")  # Debug log
            return jsonify({'success': False, 'message': 'No file selected'})
            
        if file and allowed_file(file.filename):
            # Create a file-like object in memory
            file_stream = io.BytesIO(file.read())
            
            try:
                # Open and process the image
                image = Image.open(file_stream)
                
                # Convert to RGB if necessary
                if image.mode in ('RGBA', 'P'):
                    image = image.convert('RGB')
                
                # Resize image maintaining aspect ratio
                max_size = (800, 800)
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save as JPG regardless of input format
                filename = f"{session['user_id']}_profile.jpg"
                file_path = os.path.join(profile_pics_dir, filename)
                print("Saving to:", file_path)  # Debug log
                
                # Save with optimization
                image.save(file_path, 'JPEG', quality=85, optimize=True)
                
                print("File saved successfully")  # Debug log
                
                return jsonify({
                    'success': True,
                    'message': 'Profile picture updated successfully!',
                    'filename': filename
                })
            except Exception as img_error:
                print(f"Image processing error: {str(img_error)}")  # Debug log
                return jsonify({
                    'success': False,
                    'message': 'Error processing image. Please try a different image.'
                })
        else:
            print("Invalid file type")  # Debug log
            return jsonify({
                'success': False,
                'message': 'Invalid file type. Please upload an image file (PNG, JPG, JPEG, or GIF).'
            })
            
    except Exception as e:
        print(f"Error uploading profile picture: {str(e)}")  # Debug log
        return jsonify({
            'success': False,
            'message': 'Error uploading profile picture. Please try again.'
        })

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/change_name', methods=['POST'])
def change_name():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_name = request.form.get('newName')
    if not new_name:
        flash('Name cannot be empty', 'error')
        return redirect(url_for('profile'))
    
    # Update name using SQLAlchemy
    user = User.query.get(session['user_id'])
    if user:
        user.name = new_name
        db.session.commit()
        
        # Update session
        session['user_name'] = new_name
        flash('Name updated successfully!', 'success')
    else:
        flash('User not found', 'error')
    
    return redirect(url_for('profile'))
