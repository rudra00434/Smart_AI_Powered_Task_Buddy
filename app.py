from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

Home = Flask(__name__)
Home.secret_key = "a8f9s7d6f5g4h3j2k1l0qwertyuiop"

# Gemini API Key
genai.configure(api_key="AIzaSyCGuLpyBKXhsNSAkqCKpXUHoz8zqoguF0Y")

Home.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///Task.db"
Home.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(Home)

# -------------------------
# User Model & Login Setup
# -------------------------
login_manager = LoginManager()
login_manager.init_app(Home)
login_manager.login_view = 'login'  # Redirect unauthenticated users to login


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # hashed password
    bio = db.Column(db.String(250), default="")            # new bio field
    tasks = db.relationship('Task', backref='owner', lazy=True)  # link tasks


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -------------------------
# Task Model
# -------------------------
class Task(db.Model):
    serial_no = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # Link task to user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"{self.serial_no} - {self.title} - {self.description} - {self.completed} - User {self.user_id}"


# -------------------------
# Authentication Routes
# -------------------------
@Home.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash("Username already exists!")
            return redirect(url_for('signup'))
        new_user = User(username=username, password=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        flash("Account created! Please login.")
        return redirect(url_for('login'))
    return render_template('signup.html')


@Home.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully!")
            return redirect(url_for('hello_world'))
        else:
            flash("Invalid credentials!")
            return redirect(url_for('login'))
    return render_template('login.html')


@Home.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!")
    return redirect(url_for('login'))


# -------------------------
# Existing Routes (unchanged)
# -------------------------
@Home.route('/')
@login_required
def hello_world():
    all_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()
    return render_template('index.html', tasks=all_tasks)


@Home.route("/tasks", methods=["GET", "POST"])
@login_required
def tasks():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        completed = "completed" in request.form
        new_task = Task(title=title, description=description, completed=completed, user_id=current_user.id)
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for("tasks"))
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template("tasks.html", tasks=all_tasks)


@Home.route('/task-history')
@login_required
def task_history():
    all_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()
    return render_template('task-history.html', tasks=all_tasks)


@Home.route('/chatbot')
def chatbot():
    return render_template('Chatbot.html')

@Home.route('/chat', methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").strip()

    if not user_msg:
        return jsonify({"reply": "⚠️ Please type something."})

    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")

        response = model.generate_content(
            contents=user_msg,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 200
            }
        )

        reply_text = response.text if response.text else "⚠️ No response."
        return jsonify({"reply": reply_text})

    except Exception as e:
        print("Gemini Error:", e)
        return jsonify({"reply": f"Error: {str(e)}"})


@Home.route('/about/')
def about():
    return render_template('about.html')


@Home.route('/contact')
def contact():
    return render_template('Contact.html')


@Home.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@Home.route('/api/stats')
def stats():
    total = Task.query.filter_by(
        user_id=current_user.id).count() if current_user.is_authenticated else Task.query.count()
    completed = Task.query.filter_by(user_id=current_user.id,
                                     completed=True).count() if current_user.is_authenticated else Task.query.filter_by(
        completed=True).count()
    pending = Task.query.filter_by(user_id=current_user.id,
                                   completed=False).count() if current_user.is_authenticated else Task.query.filter_by(
        completed=False).count()
    from datetime import timedelta, date
    today = date.today()
    trend = []
    for i in range(7):
        day = today - timedelta(days=i)
        count = Task.query.filter(db.func.date(Task.date_created) == day,
                                  Task.user_id == current_user.id).count() if current_user.is_authenticated else Task.query.filter(
            db.func.date(Task.date_created) == day).count()
        trend.append({"date": day.strftime("%Y-%m-%d"), "count": count})
    trend.reverse()
    return jsonify({"total": total, "completed": completed, "pending": pending, "trend": trend})


@Home.route('/delete-task/<int:task_id>', methods=["POST"])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(serial_no=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer or url_for('hello_world'))


# -------------------------
# Profile Routes (enhanced)
# -------------------------
@Home.route('/profile', methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        # Update username
        new_username = request.form.get("username")
        if new_username:
            if User.query.filter_by(username=new_username).first():
                flash("Username already exists!")
                return redirect(url_for('profile'))
            current_user.username = new_username

        # Update password
        new_password = request.form.get("password")
        if new_password:
            current_user.password = generate_password_hash(new_password)

        # Update bio
        new_bio = request.form.get("bio")
        if new_bio is not None:
            current_user.bio = new_bio

        db.session.commit()
        flash("Profile updated successfully!")
        return redirect(url_for('profile'))

    # Fetch tasks for current user
    user_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()

    # Stats
    total_tasks = len(user_tasks)
    completed_tasks = sum(1 for t in user_tasks if t.completed)
    pending_tasks = total_tasks - completed_tasks

    return render_template(
        'profile.html',
        user=current_user,
        tasks=user_tasks,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks
    )


# -------------------------
# Run App
# -------------------------
if __name__ == '__main__':
    with Home.app_context():
        db.create_all()
    Home.run(debug=True, port=8000)

