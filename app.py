from flask import Flask,send_file, request,url_for, jsonify, make_response, render_template, redirect
import psycopg2 
from functools import wraps
import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import csv
from io import BytesIO
import matplotlib.pyplot as plt
import base64

app = Flask(__name__, static_url_path='/static') 
app.config['SECRET_KEY'] = 'your secret key'

# Connect to PostgreSQL database
conn = psycopg2.connect(database="task1_database", user="postgres", password="12345", host="localhost", port="5432")
cur = conn.cursor()

# Database ORM
class User:
    def __init__(self, public_id, name, email, password):
        self.public_id = public_id
        self.name = name
        self.email = email
        self.password = password
class Period:
    def __init__(self, start_date, end_date, symptoms):
        self.start_date = start_date
        self.end_date = end_date
        self.symptoms = symptoms
class Calorie:
    def __init__(self, date, meal_name, calorie_count):
        self.date = date
        self.meal_name = meal_name
        self.calorie_count = calorie_count

# Decorator for verifying JWT
def token_required(f):
   @wraps(f)
   def decorator(*args, **kwargs):
       token = request.cookies.get('token')
    #    print("Token found in cookies:", token)
       if not token:
           return jsonify({'message': 'A valid token is missing'})
       
       try:
           data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
       except jwt.ExpiredSignatureError:
           return jsonify({'message': 'Token has expired'}), 401
       except jwt.InvalidTokenError:
           return jsonify({'message': 'Invalid token'}), 401
 
       return f(*args, **kwargs)
   return decorator

# this api endpoint is for new user signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            return make_response('User already exists. Please log in.', 202)

        hashed_password = generate_password_hash(password)
        public_id = str(uuid.uuid4())

        cur.execute("INSERT INTO users (public_id, name, email, password) VALUES (%s, %s, %s, %s)", (public_id, name, email, hashed_password))
        conn.commit()

        return redirect(url_for('login'))

    return render_template('signup.html')

# this is for login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if not user or not check_password_hash(user[3], password):
            return make_response('Invalid email or password', 401)
        # print(user[0])
        token = jwt.encode({'public_id': user[0], 'exp' : datetime.utcnow() + timedelta(minutes=30)}, app.config['SECRET_KEY'])
        # dynamic_route = f'/dashboard/{token}'
        response = make_response(redirect(url_for('dashboard')))
        response.set_cookie('token', token)
        response.set_cookie('current_user',user[0])
        return response

    return render_template('login.html')

# main webpage of the site 
@app.route('/dashboard', methods=['GET'])
@token_required
def dashboard():
    current_user = request.cookies.get('current_user')
    cur.execute("SELECT * FROM periods WHERE user_public_id = %s", (current_user,))
    periods_data = cur.fetchall()

    # Convert period history data into Period objects
    periods = [Period(start_date=row[2], end_date=row[3], symptoms=row[4]) for row in periods_data]
    cur.execute("SELECT * FROM calorie_intake WHERE user_public_id =%s",(current_user,) )
    calorie_data = cur.fetchall()
    calorie_intakes = [Calorie(date=row[2], meal_name=row[3], calorie_count=row[4]) for row in calorie_data]
    return render_template('dashboard.html', periods=periods,calorie_intakes=calorie_intakes)

# api to add period data
@app.route('/add_period', methods=['GET','POST'])
@token_required
def add_period():
    if request.method == 'POST':
        token = request.cookies.get('token')
        current_user = request.cookies.get('current_user')

        if not token:
            return jsonify({"message": "Token missing"}), 401

        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        symptoms = request.form.get('symptoms')

        if not start_date or not end_date:
            return jsonify({"message": "Start date and end date are required"}), 400

        cur.execute("INSERT INTO periods (user_public_id, start_date, end_date, symptoms) VALUES (%s, %s, %s, %s)", (current_user, start_date, end_date, symptoms))
        conn.commit()
        return jsonify({"message": "Period added successfully"}), 201

    return render_template('add_period.html')

# api to filter periods according to start/end dates
@app.route('/filter_periods', methods=['GET','POST'])
@token_required
def filter_period():
    current_user = request.cookies.get('current_user')
    periods = []

    if request.method == 'POST':
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        if not start_date or not end_date:
            return jsonify({"message": "Please provide start and end dates for filtering"}), 400

        cur.execute("SELECT * FROM periods WHERE user_public_id = %s AND start_date >= %s AND end_date <= %s", (current_user, start_date, end_date))
        periods_data = cur.fetchall()

        periods = [Period(start_date=row[2], end_date=row[3], symptoms=row[4]) for row in periods_data]

    return render_template('dashboard.html', periods=periods)

# api to analyse and find the next period timings
@app.route('/analyse_periods', methods=['POST'])
@token_required
def analyse_period():
    try:
        current_user = request.cookies.get('current_user')
        periods = []
        cur.execute("SELECT * FROM periods WHERE user_public_id = %s",(current_user,))
        periods_data = cur.fetchall()
        periods = [Period(start_date=row[2], end_date=row[3], symptoms=row[4]) for row in periods_data]

        # Calculate average time interval between periods
        if len(periods) > 1:
            total_days = sum((periods[i].end_date - periods[i-1].end_date).days for i in range(1, len(periods)))
            avg_interval = total_days / (len(periods) - 1)
        else:
            avg_interval = 28  # Default average interval if only one period is available

        # Find the latest period end date
        latest_period_end_date = max(periods, key=lambda p: p.end_date).end_date

        # Calculate the start date of the next period (assuming it's one month after the latest period)
        next_period_start_date = latest_period_end_date + timedelta(days=avg_interval)

        # Calculate the end date of the next period (assuming it's 5 days after the start date)
        next_period_end_date = next_period_start_date + timedelta(days=5)

        # Prepare the response
        next_period_start_date_str = next_period_start_date.strftime('%Y-%m-%d')
        next_period_end_date_str = next_period_end_date.strftime('%Y-%m-%d')

        # Return JSON response
        response = {
            'next_period_start_date': next_period_start_date_str,
            'next_period_end_date': next_period_end_date_str,
            # 'future_symptom': most_common_symptom
        }

        return jsonify(response),200
    except Exception as e:
        error_message = "Error analysing period: " + str(e)
        return jsonify({"error": error_message}), 500

    
# api to add the calorie intake of the user
@app.route('/add_calorie_intake', methods=['POST'])
@token_required
def add_calorie_intake():
    current_user = request.cookies.get('current_user')
    date = request.form['date']
    meal_name = request.form['meal_name']
    calorie_count = request.form['calorie_count']
    if not date or not meal_name:
            return jsonify({"message": "date and meal_name are required"}), 400

    cur.execute("INSERT INTO calorie_intake (user_public_id, date, meal_name, calorie_count) VALUES (%s, %s, %s, %s)", (current_user, date, meal_name, calorie_count))
    conn.commit()
    return jsonify({"message": "Calorie intake added successfully"}), 201

# api to get total_Calorie_intake
@app.route('/get_total_calorie_intake', methods=['GET'])
@token_required
def get_total_calorie_intake():
    current_user = request.cookies.get('current_user')

    cur.execute("SELECT SUM(calorie_count) FROM calorie_intake WHERE user_public_id = %s", (current_user,))
    total_calorie_intake = cur.fetchone()[0]

    return jsonify({"total_calorie_intake": total_calorie_intake})

# api to export and download the calorie chat as pdf
@app.route('/export_calorie_intake_pdf', methods=['GET'])
@token_required
def export_calorie_intake_pdf():
    current_user = request.cookies.get('current_user')
    
    # Retrieve calorie intake data for the current user from the database
    cur.execute("SELECT date, meal_name, calorie_count FROM calorie_intake WHERE user_public_id = %s", (current_user,))
    calorie_intakes = cur.fetchall()

    # Generate PDF
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawString(100, 750, "Calorie Intake Report")
    pdf.drawString(100, 730, "----------------------------------------------")
    y_coordinate = 710
    for intake in calorie_intakes:
        date, meal_name, calorie_count = intake
        pdf.drawString(100, y_coordinate, f"Date: {date}, Meal: {meal_name}, Calorie Count: {calorie_count}")
        y_coordinate -= 20
    pdf.save()

    # Return PDF file
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True,download_name="calorie_intake_report.pdf")

# api to download the calorie as csv
@app.route('/export_calorie_intake_csv', methods=['GET'])
@token_required
def export_calorie_intake_csv():
    current_user = request.cookies.get('current_user')

    # Retrieve calorie intake data for the current user from the database
    cur.execute("SELECT date, meal_name, calorie_count FROM calorie_intake WHERE user_public_id = %s", (current_user,))
    calorie_intakes = cur.fetchall()

    # Generate CSV
    csv_data = [['Date', 'Meal Name', 'Calorie Count']]
    for intake in calorie_intakes:
        csv_data.append(list(intake))
        
    # Convert CSV data to string
    csv_content = '\n'.join([','.join(map(str, row)) for row in csv_data])
    # Convert string to bytes
    csv_bytes = csv_content.encode()

    # Return CSV file
    output = BytesIO()
    output.write(csv_bytes)
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name="calorie_intake_report.csv")

# api to visualize the calorie instakes 
@app.route('/calorie_intake_visualization', methods=['GET'])
@token_required
def calorie_intake_visualization():
    current_user = request.cookies.get('current_user')
    
    # Retrieve calorie intake data for the current user from the database
    cur.execute("SELECT date, calorie_count FROM calorie_intake WHERE user_public_id = %s", (current_user,))
    calorie_intakes = cur.fetchall()

    # Extract dates and calorie counts
    dates = [row[0] for row in calorie_intakes]
    calorie_counts = [row[1] for row in calorie_intakes]
    print()

    # Generate daily, weekly, and monthly calorie intake data
    daily_data = {}
    weekly_data = {}
    monthly_data = {}
    for date, calorie_count in zip(dates, calorie_counts):
        daily_key = date.strftime('%Y-%m-%d')
        if daily_key not in daily_data:
            daily_data[daily_key] = 0
        daily_data[daily_key] += calorie_count

        start_of_week = date - timedelta(days=date.weekday())
        weekly_key = start_of_week.strftime('%Y-%m-%d')
        if weekly_key not in weekly_data:
            weekly_data[weekly_key] = 0
        weekly_data[weekly_key] += calorie_count

        start_of_month = date.replace(day=1)
        monthly_key = start_of_month.strftime('%Y-%m-%d')
        if monthly_key not in monthly_data:
            monthly_data[monthly_key] = 0
        monthly_data[monthly_key] += calorie_count

    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(list(daily_data.keys()), list(daily_data.values()), label='Daily Calorie Intake')
    plt.plot(list(weekly_data.keys()), list(weekly_data.values()), label='Weekly Calorie Intake')
    plt.plot(list(monthly_data.keys()), list(monthly_data.values()), label='Monthly Calorie Intake')
    plt.xlabel('Date')
    plt.ylabel('Calorie Intake')
    plt.title('Calorie Intake Over Time')
    plt.legend()
    plt.grid(True)

    # Save the plot to a buffer
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)

    # Encode the buffer contents as base64
    encoded_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    return jsonify({
        'image': encoded_image,
        'daily_dates': list(daily_data.keys()),
        'daily_calories': list(daily_data.values()),
        'weekly_dates': list(weekly_data.keys()),
        'weekly_calories': list(weekly_data.values()),
        'monthly_dates': list(monthly_data.keys()),
        'monthly_calories': list(monthly_data.values())
    })


if __name__ == '__main__':
    app.run(debug=True)
