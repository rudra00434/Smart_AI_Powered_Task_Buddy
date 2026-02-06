from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import google.generativeai as genai
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import NullPool
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SESSION_COOKIE_SAMESITE'] = "Lax"
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True

# -------------------------
# Secret Key (Env Safe)
# -------------------------
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# -------------------------
# Gemini API Key (Env Safe)
# -------------------------
api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

# -------------------------
# Database Config (Vercel Safe)
# -------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, "Task.db")

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{db_path}"
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "poolclass": NullPool
}

db = SQLAlchemy()
db.init_app(app)

# -------------------------
# Login Manager Setup
# -------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# -------------------------
# User Model
# -------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"   # <-- ADD THIS

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.String(250), default="")
    tasks = db.relationship('Task', backref='owner', lazy=True)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))




class Task(db.Model):
    __tablename__ = "tasks"   # <-- ADD THIS

    serial_no = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    # CHANGE FOREIGN KEY
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# AUTH ROUTES
# -------------------------
@app.route('/signup', methods=["GET", "POST"])
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

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/login', methods=["GET", "POST"])
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully!")
    return redirect(url_for('login'))

# -------------------------
# MAIN ROUTES
# -------------------------
@app.route('/')
@login_required
def hello_world():
    all_tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()
    return render_template('index.html', tasks=all_tasks)

@app.route("/tasks", methods=["GET", "POST"])
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

@app.route('/chatbot')
def chatbot():
    return render_template('Chatbot.html')

@app.route('/chat', methods=["POST"])
def chat():
    user_msg = request.json.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "⚠️ Please type something."})
    try:
        model = genai.GenerativeModel("models/gemini-flash-latest")
        response = model.generate_content(user_msg)
        reply_text = response.text if response.text else "⚠️ No response."
        return jsonify({"reply": reply_text})
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

@app.route('/about/')
def about():
    return render_template('about.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# -------------------------
# PROFILE
# -------------------------
@app.route('/profile', methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        new_username = request.form.get("username")
        if new_username:
            if User.query.filter_by(username=new_username).first():
                flash("Username already exists!")
                return redirect(url_for('profile'))
            current_user.username = new_username

        new_password = request.form.get("password")
        if new_password:
            current_user.password = generate_password_hash(new_password)

        db.session.commit()
        flash("Profile updated successfully!")
        return redirect(url_for('profile'))

    user_tasks = Task.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, tasks=user_tasks)

if __name__ == '__main__':
    app.run(debug=True)

