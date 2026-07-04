"""
AI-Powered Study Companion App

Author: Emily Moeletsi

Description:
A Flask web application that helps students improve their learning by determining their preffered
learning style, generating personalized study plans, managing uploaded study materials, and creating
AI-inspired quizzes.
"""

# Required Import Libraries
from flask import Flask, render_template, request, redirect, session
from werkzeug.utils import secure_filename
import sqlite3
import os
from PyPDF2 import PdfReader
import docx

#Application settings configuration
app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
ALLOWED_EXTENSIONS = {"txt", "pdf", "doc", "docx"}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def get_db():
    return sqlite3.connect("database.db")
    """
    Establish and return a connection to the SQLite database.
    """

#Database Table Creation
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            learning_style TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            score INTEGER,
            taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    
    conn.commit()
    conn.close()
    
init_db()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS
    """
    Check whether the uploaded file has a supported extension.
    """
# ======================================
# User Authentication Routes
# ======================================
@app.route("/", methods = ["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        if not email or not password:
            return render_template("login.html", error = "Please enter email amd password")
        
        email = email.strip().lower()
        password = password.strip()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND password=?",(email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user is not None:
            session["user_id"] = user[0]
            return redirect("/dashboard")
        else:
            return render_template("login.html", error = "Invalid email or password")
        
    return render_template("login.html")
    
# ======================================
# User Registration
# ======================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            return render_template("register.html", error="Enter email and password")

        email = email.strip().lower()
        password = password.strip()

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password) VALUES (?,?)",
                (email, password)
            )
            conn.commit()
            conn.close()
            return redirect("/")
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Email already exists")

    return render_template("register.html")

# ======================================
# Dashboard
# ======================================
@app.route("/dashboard")
def dashboard():
    """
    Display the user's dashboard including
    learning style and uploaded study materials.
    """
    
    # Redirect if user is not logged in
    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cursor = conn.cursor()

    #  Get User's learning style 
    cursor.execute("SELECT learning_style FROM users WHERE id=?", (session["user_id"],))
    
    user_info = cursor.fetchone()
    
    if not user_info or user_info[0] is None:
        conn.close()
        return redirect("/quiz")  # redirect if no learning style set
    
    learning_style = user_info[0]

    #  Getting the latest uploaded file for the user
    cursor.execute("""
        SELECT filename, uploaded_at 
        FROM uploads 
        WHERE user_id = ?
        ORDER BY uploaded_at DESC
    """, (session["user_id"],))
    
    files = cursor.fetchall()# showa no files uploaded yet
    
    conn.close()

    # Rendering dashboard with learning style and file info
    return render_template("dashboard.html", learning_style=learning_style, files=files)


# ======================================
# File Upload
# ====================================== 
@app.route("/upload", methods=["GET", "POST"])
def upload():

    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":

        if "file" not in request.files:
            return render_template("upload.html", error="No file selected")

        file = request.files["file"]

        if file.filename == "":
            return render_template("upload.html", error="No file selected")

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Store the uploaded study material so it can be analyzed later.
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            # Record the uploaded file in the database and associate it with the logged-in user.
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO uploads (user_id, filename) VALUES (?, ?)",
                (session["user_id"], filename)
            )
            conn.commit()
            conn.close()

            return redirect("/dashboard")

        else:
            return render_template("upload.html", error="File type not allowed")

    return render_template("upload.html")



#Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ======================================
# Learning Style Quiz
# ======================================
@app.route("/quiz", methods = ["GET", "POST"])
def quiz():
    if "user_id" not in session:
        return redirect("/")
    
    if request.method == "POST":
        visual = 0
        auditory = 0
        reading = 0
        kinaesthetic = 0
        
        answers = request.form
        
        for answer in answers.values():
            if answer == "Visual":
                visual += 1
            elif answer == "Auditory":
                auditory += 1
            elif answer == "Reading":
                reading += 1
            elif answer == "Kinaesthetic":
                kinaesthetic += 1
                
        learning_style = max(
            [("visual", visual), ("auditory", auditory), ("reading", reading), ("kinaesthetic", kinaesthetic)],
            key = lambda x: x[1]
        )[0]
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET learning_style=? WHERE id=?",
            (learning_style, session["user_id"])
        )
        
        score = max(visual, auditory, reading, kinaesthetic)

        cursor.execute(
            "INSERT INTO progress (user_id, score) VALUES (?, ?)",
            (session["user_id"], score)
        )

        conn.commit()
        conn.close()
        
        return redirect("/dashboard")
    
    return render_template("quiz.html")

# ======================================
# Personalized Study Plan
# ======================================
@app.route("/study-plan", methods=["POST"])
def study_plan():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT learning_style FROM users WHERE id=?",
        (session["user_id"],)
    )

    result = cursor.fetchone()

    learning_style = result[0] if result else "General"
    
    
    cursor.execute("""
        SELECT filename
        FROM uploads
        WHERE user_id = ?
    """, (session["user_id"],))

    files = cursor.fetchall()

    plan = []
    
    upload_folder = app.config["UPLOAD_FOLDER"]

    if files:
        for f in files:
            filename = f[0]
            file_path = os.path.join(upload_folder, filename)

            content = extract_text(file_path)
            content = content[:1000]  # limit

            if content.strip():
                plan.append(f"📘 Study: {filename}")
                plan.append(f"Key preview: {content[:200]}...")

                if "definition" in content.lower():
                    plan.append("📌 Focus on definitions")

                if "example" in content.lower():
                    plan.append("🧠 Practice examples")

                if "exam" in content.lower():
                    plan.append("⚠ Focus on exam questions")
    else:
        plan.append("Upload study materials for AI-generated plan")

    if learning_style == "Visual":
        base_plan = [
            "Read notes and create mind maps",
            "Watch educational videos",
            "Review diagrams and charts",
            "Complete a visual summary"
        ]

    elif learning_style == "Auditory":
        base_plan = [
            "Listen to recorded lectures",
            "Discuss concepts aloud",
            "Use text-to-speech tools",
            "Review key topics verbally"
        ]

    elif learning_style == "Kinesthetic":
        base_plan = [
            "Practice exercises",
            "Build examples/projects",
            "Use flashcards actively",
            "Take frequent practice tests"
        ]

    else:
        base_plan = [
            "Read study materials",
            "Take notes",
            "Review concepts",
            "Complete a self-test"
        ]

    plan.extend(base_plan)

    conn.close()

    return render_template(
        "study_plan.html",
        learning_style=learning_style,
        plan=plan
    )


def extract_text(file_path):
    """
    Check whether the uploaded file has a supported extension.
    """
    ext = file_path.split(".")[-1].lower()

    text = ""

    # PDF
    if ext == "pdf":
        reader = PdfReader(file_path)
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text()

    # DOCX
    elif ext == "docx":
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"

    # TXT
    elif ext == "txt":
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

    return text


# ======================================
# AI Quiz Generation
# ======================================
@app.route("/ai_quiz", methods=["POST"])
def ai_quiz():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db()
    cursor = conn.cursor()

    # Get uploaded files
    cursor.execute("""
        SELECT filename
        FROM uploads
        WHERE user_id = ?
    """, (session["user_id"],))

    files = cursor.fetchall()

    upload_folder = app.config["UPLOAD_FOLDER"]
    
    questions = []
    
    for f in files:
        filename = f[0]
        file_path = os.path.join(upload_folder, filename)

        content = extract_text(file_path)

        # Break the extracted text into smaller sections for question generation.
        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # Ignore very short lines because they usually do not contain enough information to create meaningful questions.
            if len(line) < 20:
                continue

            # Create simple fill-in-the-blank questions
            words = line.split()

            if len(words) > 5:
                answer = words[0]
                question_text = line.replace(answer, "_____ ", 1)

                questions.append({
                    "question": question_text,
                    "answer": answer
                })

            # Limit number of questions
            if len(questions) >= 10:
                break

        if len(questions) >= 10:
            break

    conn.close()

    if not questions:
        questions.append({
            "question": "No study material found. Upload notes first.",
            "answer": ""
        })

    return render_template(
        "ai_quiz.html",
        questions=questions
    )

if __name__ == "__main__":
    app.run(debug=True)