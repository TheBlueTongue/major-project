from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from database_setup import SessionLocal, User, EBike, PracticeTest, RealTest, ParkingSpot, PracticeAttempt, PracticeQuestion, RealTestAttempt
import forms
from datetime import datetime
from forms import PracticeQuizForm



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

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = forms.RegisterForm()
    if form.validate_on_submit():
        session = SessionLocal()
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(
            username=form.username.data,
            email=form.email.data, 
            password=hashed_password
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

# Route for the dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    session = SessionLocal()
    ebike_count = session.query(EBike).filter_by(owner_id=current_user.id).count()
    PASSING_SCORE = 80

    completed_practice_tests = (
        session.query(PracticeAttempt)
        .filter(
            PracticeAttempt.user_id == current_user.id,
            PracticeAttempt.score >= PASSING_SCORE
        )
        .count()
    )

    total_tests = session.query(RealTest).filter_by(user_id=current_user.id).count()
    available_parking_spots = session.query(ParkingSpot).filter_by(is_available=True).count()
    session.close()
    return render_template(
        'dashboard.html',
        ebike_count=ebike_count,
        completed_practice_tests=completed_practice_tests,
        available_parking_spots=available_parking_spots,
        total_tests=total_tests
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


@app.route('/practice', methods=['GET', 'POST'])
@login_required
def practice_quiz():
    session = SessionLocal()  # Create a new session
    questions = session.query(PracticeQuestion).all()  # Fetch questions
    form = PracticeQuizForm()
    
    # Populate the form with questions if it's a GET request
    if request.method == 'GET':
        form.question.choices = [
            (q.id, f"{q.question_text}\nA. {q.option_a}  B. {q.option_b}  C. {q.option_c}  D. {q.option_d}") 
            for q in questions
        ]
        session.close()  # Close the session after GET request
        return render_template('practice_quiz.html', form=form)

    # Handle the form submission
    if form.validate_on_submit():
        score = 0
        for question in questions:
            selected_answer = request.form.get(str(question.id))
            if selected_answer == question.correct_answer:
                score += 1
        
        # Save the attempt
        attempt = PracticeAttempt(user_id=current_user.id, score=score)
        session.add(attempt)
        session.commit()
        
        flash(f"You scored {score}/{len(questions)}", "success")
        session.close()  # Close the session after POST request
        return redirect(url_for('practice_quiz'))
    
    flash("Please select an answer for each question.", "danger")
    session.close()  # Close the session if form is not submitted
    return render_template('practice_quiz.html', form=form)

@app.route('/parking_spots')
@login_required
def parking_spots():
    session = SessionLocal()
    spots = session.query(ParkingSpot).all()
    session.close()
    return render_template('parking_spots.html', spots=spots)

@app.route('/real_tests')
@login_required
def real_tests():
    return render_template('real_tests.html')

# Route for user profile
@app.route('/profile')
@login_required
def user_profile():
    return render_template('user_profile.html')

if __name__ == '__main__':
    app.run(debug=True)

