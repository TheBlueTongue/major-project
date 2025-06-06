from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from database_setup import SessionLocal, User, EBike, PracticeTest, RealTest, ParkingSpot, PracticeAttempt, PracticeQuestion, RealTestAttempt, PracticeTest
import forms
from datetime import datetime
from flask import Flask
from flask.cli import with_appcontext
from database_setup import SessionLocal, PracticeTest, PracticeQuestion, Area
import click
import random
from collections import defaultdict
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import os
import pandas as pd
from sqlalchemy.orm import joinedload




# Set up Flask app and login manager
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key12345asdfg'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if user is not authenticated

# Session management function which retrieves the user from the database
@login_manager.user_loader
def load_user(user_id):
    session = SessionLocal()
    user = session.query(User).get(int(user_id))
    session.close()
    return user

# Welcome page route
@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = forms.RegisterForm()
    if form.validate_on_submit():
        session = SessionLocal()
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password,
            role=form.role.data,
            department=form.department.data if form.role.data == 'teacher' else None,
            year=int(form.year.data) if form.role.data == 'student' and form.year.data else None,
            house=form.house.data if form.role.data == 'student' else None
        )
        session.add(new_user)
        try:
            session.commit()
            flash('Account created successfully!', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            session.rollback()
            flash('Username already exists. Please choose a different one.', 'danger')
        finally:
            session.close()
    return render_template('register.html', form=form)


# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = forms.LoginForm()
    if form.validate_on_submit():
        session = SessionLocal()
        user = session.query(User).filter_by(username=form.username.data).first()
        session.close()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

# Route for logging out
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    session = SessionLocal()
    ebike_count = session.query(EBike).filter_by(owner_id=current_user.id).count()
    completed_practice_tests = session.query(PracticeAttempt).filter(
        PracticeAttempt.user_id == current_user.id,
        PracticeAttempt.score >= 80
    ).count()
    total_tests = session.query(RealTest).filter_by(user_id=current_user.id).count()
    available_parking_spots = session.query(ParkingSpot).filter_by(is_available=True).count()
    practice_tests = session.query(PracticeTest).filter_by(user_id=current_user.id).all()
    session.close()
    return render_template(
        'dashboard.html',
        ebike_count=ebike_count,
        completed_practice_tests=completed_practice_tests,
        available_parking_spots=available_parking_spots,
        total_tests=total_tests,
        practice_tests=practice_tests
    )

@app.route('/ebikes', methods=['GET', 'POST'])
@login_required
def ebike_management():
    session = SessionLocal()
    form = forms.EbikeRegistrationForm()
    ebikes = session.query(EBike).filter_by(owner_id=current_user.id).all()

    # Check if the user has passed the real test
    passed_test = session.query(RealTestAttempt).filter(
        RealTestAttempt.user_id == current_user.id,
        RealTestAttempt.passed == True
    ).count() > 0

    # Handle e-bike registration
    if form.validate_on_submit():
        new_ebike = EBike(
            owner_id=current_user.id,
            model=form.model.data,
            serial_number=form.serial_number.data,
            colour=form.colour.data
        )
        try:
            session.add(new_ebike)
            session.commit()
            flash('E-bike registered successfully!', 'success')
        except IntegrityError:
            session.rollback()
            flash('This serial number is already registered. Please use a unique serial number.', 'danger')
        return redirect(url_for('ebike_management'))

    # Handle e-bike deletion
    if request.method == 'POST' and 'delete_ebike_id' in request.form:
        ebike_id = int(request.form.get('delete_ebike_id'))
        ebike_to_delete = session.query(EBike).filter_by(id=ebike_id, owner_id=current_user.id).first()
        if ebike_to_delete:
            session.delete(ebike_to_delete)
            session.commit()
            flash('E-bike deleted successfully!', 'success')
        return redirect(url_for('ebike_management'))
    
    session.close()
    return render_template('ebike_management.html', ebikes=ebikes, form=form, passed_test=passed_test)


@app.route('/reserve_spot', methods=['POST'])
@login_required
def reserve_spot():
    session = SessionLocal()
    spot_id = request.form.get('spot_id')
    selected_date = request.form.get('selected_date', date.today().isoformat())
    reservation_date = datetime.strptime(selected_date, "%Y-%m-%d").date()

    spot = session.query(ParkingSpot)\
    .options(joinedload(ParkingSpot.reserved_user))\
    .filter_by(id=spot_id)\
    .first()

    if not spot or (spot.reservation_date == reservation_date and not spot.is_available):
        flash("This spot is no longer available for that date.", "danger")
        session.close()
        return redirect(f'/parking_spots?date={selected_date}')

    spot.is_available = False
    spot.reserved_for = current_user.id
    spot.reservation_date = reservation_date
    session.commit()
    flash("Spot reserved successfully!", "success")

    session.close()
    return redirect(f'/parking_spots?date={selected_date}')



@app.route('/release_spot', methods=['POST'])
@login_required
def release_spot():
    session = SessionLocal()
    spot_id = request.form.get('spot_id')
    selected_date = request.form.get('selected_date', date.today().isoformat())

    spot = session.query(ParkingSpot).get(spot_id)

    if spot and spot.reserved_for == current_user.id:
        spot.is_available = True
        spot.reserved_for = None
        spot.reservation_date = None
        session.commit()
        flash("Spot released.", "info")

    session.close()
    return redirect(f'/parking_spots?date={selected_date}')


@app.route("/parking_spots", methods=["GET"])
@login_required
def parking_spots():
    session = SessionLocal()

    selected_date_str = request.args.get("date")
    selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date() if selected_date_str else date.today()

    # Eager load reserved_user to avoid DetachedInstanceError
    spots = session.query(ParkingSpot).options(joinedload(ParkingSpot.reserved_user)).all()

    spots_by_number = {spot.number: spot for spot in spots}

    base_dir = os.path.dirname(os.path.abspath(__file__))
    map_path = os.path.join(base_dir, "Map.xlsx")
    layout_df = pd.read_excel(map_path, header=None).iloc[0:30, 0:42].fillna("").astype(str)
    layout_grid = layout_df.values.tolist()

    session.close()

    return render_template(
        "parking_spots.html",
        layout_grid=layout_grid,
        spots_by_number=spots_by_number,
        selected_date=selected_date,
        timedelta=timedelta
    )





@app.route('/seed_parking_spots')
def seed_parking_spots():
    session = SessionLocal()
    for i in range(1, 101):
        spot = ParkingSpot(number=f"OS-{i}", area=Area.OLD_SCHOOL)
        session.add(spot)
    for i in range(1, 51):
        spot = ParkingSpot(number=f"SG-{i}", area=Area.SIDE_GATE)
        session.add(spot)
    session.commit()
    session.close()
    return "Seeded parking spots!"

@app.route('/real_tests')
@login_required
def real_tests():
    return render_template('real_tests.html')

# Route for user profile
@app.route('/profile')
@login_required
def user_profile():
    return render_template('user_profile.html')

@app.route('/practice', methods=['GET'])
@login_required
def practice_selection():
    # Create a new session for this route
    session = SessionLocal()
    
    # Fetch the current user with their practice attempts
    user = session.query(User).filter_by(id=current_user.id).first()
    tests = session.query(PracticeTest).all()
    attempts = {attempt.test_id: attempt for attempt in user.practice_attempts}
    
    # Close the session
    session.close()
    
    # Render the page
    return render_template('practice_selection.html', tests=tests, attempts=attempts)


@app.route('/practice/<int:test_id>', methods=['GET', 'POST'])
@login_required
def practice_quiz(test_id):
    session = SessionLocal()
    test = session.query(PracticeTest).filter_by(id=test_id).first()

    if not test:
        flash("Quiz not found.", "danger")
        session.close()
        return redirect(url_for('practice_selection'))

    # Randomise and fetch up to 20 questions
    questions = random.sample(test.questions, min(20, len(test.questions)))

    if request.method == 'POST':
        score = 0
        total = len(questions)

        for question in questions:
            user_answer = request.form.get(str(question.id))
            if user_answer == question.correct_answer:
                score += 1

        # Save the attempt
        attempt = PracticeAttempt(user_id=current_user.id, test_id=test_id, score=score)
        session.add(attempt)
        session.commit()
        session.close()

        flash(f"You scored {score}/{total}", "success")
        return redirect(url_for('practice_selection'))

    session.close()
    return render_template('practice_quiz.html', test=test, questions=questions)



@app.cli.command("populate-practice-questions")
@with_appcontext
def populate_practice_questions():
    session = SessionLocal()

    quiz_names = [
        "Basic E-Bike Safety in Australia",
        "Traffic Rules and Signs for E-Bikes",
        "E-Bike Maintenance and Emergency Handling"
    ]

    questions_data = {
        "Basic E-Bike Safety in Australia": [
            "What should you always wear when riding an e-bike?",
            "Is it legal to ride an e-bike without a helmet in Australia?",
            "What is the maximum speed allowed for e-bikes in Australia?",
            "How should you position yourself on the road when riding an e-bike?",
            "What should you do before riding your e-bike for the first time?"
        ],
        "Traffic Rules and Signs for E-Bikes": [
            "What does the red traffic light signify?",
            "Can you ride on footpaths in Australia with an e-bike?",
            "What should you do when approaching a pedestrian crossing?",
            "How should you signal a turn on an e-bike?",
            "What does a yellow bike lane sign mean?"
        ],
        "E-Bike Maintenance and Emergency Handling": [
            "What is the recommended tire pressure for an e-bike?",
            "How do you check the brakes on your e-bike?",
            "What should you do if your e-bike’s battery dies during a ride?",
            "How often should you clean your e-bike?",
            "What should you do if you experience a flat tire?"
        ]
    }

    for quiz_name in quiz_names:
        test = PracticeTest(name=quiz_name, user_id=1)
        session.add(test)
        session.commit()

        questions = questions_data[quiz_name]
        for i in range(20):
            q_text = questions[i % len(questions)]
            question = PracticeQuestion(
                test_id=test.id,
                question_text=q_text,
                option_a="Option A",
                option_b="Option B",
                option_c="Option C",
                option_d="Option D",
                correct_answer="A"
            )
            session.add(question)
        session.commit()

    session.close()
    print("Practice tests and questions populated successfully.")



if __name__ == '__main__':
    app.run(debug=True)

