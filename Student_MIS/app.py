from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from models import db, Student, Course, Enrollment, Communication, Resource, AuditLog
from datetime import datetime, timedelta
from sqlalchemy import func
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'mis-secret-key-2024'
db.init_app(app)

# ─────────────────────────────────────────────
# CORE ENGINE: Fixed Categorization Logic
# ─────────────────────────────────────────────
def categorize_student(marks, attendance):
    """Fixed logic: validation FIRST, then categorization."""
    # Validate ranges FIRST (was broken before — checked after valid ranges)
    if marks < 0 or marks > 100 or attendance < 0 or attendance > 100:
        return "Invalid"
    if marks >= 75 and attendance >= 80:
        return "Excellent"
    elif marks >= 50 and attendance >= 60:
        return "Average"
    else:
        return "At Risk"

def get_risk_score(marks, attendance):
    """DSS: Composite risk score 0-100 (higher = more at risk)."""
    mark_risk = max(0, (75 - marks) / 75) * 60
    att_risk   = max(0, (80 - attendance) / 80) * 40
    return round(min(100, mark_risk + att_risk), 1)

def dss_recommendations(student):
    """DSS: Generate actionable intervention recommendations."""
    recs = []
    if student.marks < 40:
        recs.append({"type": "urgent", "action": "Immediate remedial tutoring required", "module": "Academic"})
    elif student.marks < 60:
        recs.append({"type": "warning", "action": "Schedule one-on-one counselling session", "module": "Academic"})
    if student.attendance < 60:
        recs.append({"type": "urgent", "action": "Contact parent/guardian immediately", "module": "Attendance"})
    elif student.attendance < 75:
        recs.append({"type": "warning", "action": "Issue attendance warning notice", "module": "Attendance"})
    if student.marks >= 85 and student.attendance >= 90:
        recs.append({"type": "positive", "action": "Nominate for merit scholarship", "module": "Recognition"})
    if not recs:
        recs.append({"type": "info", "action": "Student on track — continue monitoring", "module": "General"})
    return recs

# ─────────────────────────────────────────────
# ESS — Executive Support System (Dashboard)
# ─────────────────────────────────────────────
@app.route('/')
def index():
    students = Student.query.filter_by(is_active=True).all()
    return render_template('index.html', students=students)

@app.route('/ess/dashboard')
def ess_dashboard():
    students = Student.query.filter_by(is_active=True).all()
    total = len(students)
    if total == 0:
        stats = {"total": 0, "excellent": 0, "average": 0, "at_risk": 0, "invalid": 0,
                 "avg_marks": 0, "avg_attendance": 0, "pass_rate": 0}
    else:
        excellent  = sum(1 for s in students if s.category == "Excellent")
        average    = sum(1 for s in students if s.category == "Average")
        at_risk    = sum(1 for s in students if s.category == "At Risk")
        invalid    = sum(1 for s in students if s.category == "Invalid")
        avg_marks  = round(sum(s.marks for s in students) / total, 1)
        avg_att    = round(sum(s.attendance for s in students) / total, 1)
        pass_rate  = round((excellent + average) / total * 100, 1)
        stats = {"total": total, "excellent": excellent, "average": average,
                 "at_risk": at_risk, "invalid": invalid,
                 "avg_marks": avg_marks, "avg_attendance": avg_att, "pass_rate": pass_rate}

    # Category distribution for chart
    chart_data = {
        "labels": ["Excellent", "Average", "At Risk"],
        "values": [stats.get("excellent", 0), stats.get("average", 0), stats.get("at_risk", 0)],
        "colors": ["#10b981", "#f59e0b", "#ef4444"]
    }
    # Marks distribution buckets
    buckets = {"0-40": 0, "41-60": 0, "61-75": 0, "76-100": 0}
    for s in students:
        if s.marks <= 40:   buckets["0-40"] += 1
        elif s.marks <= 60: buckets["41-60"] += 1
        elif s.marks <= 75: buckets["61-75"] += 1
        else:               buckets["76-100"] += 1

    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(8).all()
    return render_template('ess_dashboard.html', stats=stats,
                           chart_data=json.dumps(chart_data),
                           buckets=json.dumps(buckets),
                           recent_logs=recent_logs)

# ─────────────────────────────────────────────
# STUDENT CRUD (core)
# ─────────────────────────────────────────────
@app.route('/students')
def students_list():
    q        = request.args.get('q', '')
    category = request.args.get('category', '')
    students = Student.query.filter_by(is_active=True)
    if q:        students = students.filter(Student.name.ilike(f'%{q}%'))
    if category: students = students.filter_by(category=category)
    students = students.order_by(Student.name).all()
    return render_template('students.html', students=students, q=q, selected_cat=category)

@app.route('/add', methods=['GET', 'POST'])
def add_student():
    courses = Course.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        name       = request.form['name'].strip()
        marks      = float(request.form['marks'])
        attendance = float(request.form['attendance'])
        email      = request.form.get('email', '').strip()
        phone      = request.form.get('phone', '').strip()
        course_id  = request.form.get('course_id')

        # Validation
        errors = []
        if not name:             errors.append("Name is required.")
        if marks < 0 or marks > 100:       errors.append("Marks must be between 0 and 100.")
        if attendance < 0 or attendance > 100: errors.append("Attendance must be between 0 and 100.")
        if errors:
            for e in errors: flash(e, 'danger')
            return render_template('add.html', courses=courses)

        category   = categorize_student(marks, attendance)
        risk_score = get_risk_score(marks, attendance)
        student    = Student(name=name, marks=marks, attendance=attendance,
                             category=category, email=email, phone=phone,
                             risk_score=risk_score, enrolled_date=datetime.utcnow())
        db.session.add(student)
        db.session.flush()

        if course_id:
            enroll = Enrollment(student_id=student.id, course_id=int(course_id),
                                enrolled_on=datetime.utcnow(), status="Active")
            db.session.add(enroll)

        log = AuditLog(action=f"Added student: {name} ({category})", module="Student", timestamp=datetime.utcnow())
        db.session.add(log)
        db.session.commit()
        flash(f"Student '{name}' added successfully — categorized as {category}.", 'success')
        return redirect(url_for('students_list'))
    return render_template('add.html', courses=courses)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    student = Student.query.get_or_404(id)
    courses = Course.query.filter_by(is_active=True).all()
    if request.method == 'POST':
        student.name       = request.form['name'].strip()
        student.marks      = float(request.form['marks'])
        student.attendance = float(request.form['attendance'])
        student.email      = request.form.get('email', '').strip()
        student.phone      = request.form.get('phone', '').strip()

        errors = []
        if student.marks < 0 or student.marks > 100:
            errors.append("Marks must be between 0 and 100.")
        if student.attendance < 0 or student.attendance > 100:
            errors.append("Attendance must be between 0 and 100.")
        if errors:
            for e in errors: flash(e, 'danger')
            return render_template('edit.html', student=student, courses=courses)

        student.category   = categorize_student(student.marks, student.attendance)
        student.risk_score = get_risk_score(student.marks, student.attendance)
        log = AuditLog(action=f"Updated student: {student.name}", module="Student", timestamp=datetime.utcnow())
        db.session.add(log)
        db.session.commit()
        flash("Student updated successfully.", 'success')
        return redirect(url_for('students_list'))
    return render_template('edit.html', student=student, courses=courses)

@app.route('/delete/<int:id>', methods=['POST'])
def delete_student(id):
    student = Student.query.get_or_404(id)
    student.is_active = False   # Soft delete
    log = AuditLog(action=f"Deactivated student: {student.name}", module="Student", timestamp=datetime.utcnow())
    db.session.add(log)
    db.session.commit()
    flash(f"Student '{student.name}' removed.", 'warning')
    return redirect(url_for('students_list'))

@app.route('/student/<int:id>')
def student_detail(id):
    student = Student.query.get_or_404(id)
    recs    = dss_recommendations(student)
    comms   = Communication.query.filter_by(student_id=id).order_by(Communication.sent_on.desc()).limit(5).all()
    enrolments = Enrollment.query.filter_by(student_id=id).all()
    return render_template('studentDetails.html', student=student,
                           recommendations=recs, communications=comms, enrolments=enrolments)

# ─────────────────────────────────────────────
# DSS — Decision Support System
# ─────────────────────────────────────────────
@app.route('/dss')
def dss():
    students = Student.query.filter_by(is_active=True).order_by(Student.risk_score.desc()).all()
    at_risk  = [s for s in students if s.category == "At Risk"]
    all_recs = []
    for s in at_risk[:10]:
        for r in dss_recommendations(s):
            all_recs.append({"student": s.name, "id": s.id, **r})
    return render_template('dss.html', students=students, recommendations=all_recs, at_risk_count=len(at_risk))

# ─────────────────────────────────────────────
# ERP — Course & Resource Management
# ─────────────────────────────────────────────
@app.route('/erp/courses')
def erp_courses():
    courses   = Course.query.filter_by(is_active=True).all()
    resources = Resource.query.all()
    return render_template('erp_courses.html', courses=courses, resources=resources)

@app.route('/erp/courses/add', methods=['POST'])
def erp_add_course():
    name     = request.form['name'].strip()
    code     = request.form['code'].strip()
    credits  = int(request.form.get('credits', 3))
    capacity = int(request.form.get('capacity', 60))
    if name and code:
        course = Course(name=name, code=code, credits=credits, capacity=capacity)
        db.session.add(course)
        log = AuditLog(action=f"Added course: {name} ({code})", module="ERP", timestamp=datetime.utcnow())
        db.session.add(log)
        db.session.commit()
        flash(f"Course '{name}' added.", 'success')
    return redirect(url_for('erp_courses'))

@app.route('/erp/resources/add', methods=['POST'])
def erp_add_resource():
    title    = request.form['title'].strip()
    rtype    = request.form.get('type', 'Book')
    quantity = int(request.form.get('quantity', 1))
    if title:
        res = Resource(title=title, resource_type=rtype, quantity=quantity, available=quantity)
        db.session.add(res)
        db.session.commit()
        flash(f"Resource '{title}' added.", 'success')
    return redirect(url_for('erp_courses'))

# ─────────────────────────────────────────────
# CRM — Student Relationship Management
# ─────────────────────────────────────────────
@app.route('/crm')
def crm():
    students = Student.query.filter_by(is_active=True).all()
    comms    = Communication.query.order_by(Communication.sent_on.desc()).limit(20).all()
    return render_template('crm.html', students=students, communications=comms)

@app.route('/crm/communicate', methods=['POST'])
def crm_communicate():
    student_id = int(request.form['student_id'])
    message    = request.form['message'].strip()
    comm_type  = request.form.get('type', 'Email')
    student    = Student.query.get_or_404(student_id)
    comm = Communication(student_id=student_id, message=message,
                         comm_type=comm_type, sent_on=datetime.utcnow(), status="Sent")
    db.session.add(comm)
    log = AuditLog(action=f"CRM: {comm_type} sent to {student.name}", module="CRM", timestamp=datetime.utcnow())
    db.session.add(log)
    db.session.commit()
    flash(f"{comm_type} logged for {student.name}.", 'success')
    return redirect(url_for('crm'))

# ─────────────────────────────────────────────
# SCM — Academic Supply Chain Management
# ─────────────────────────────────────────────
@app.route('/scm')
def scm():
    resources    = Resource.query.all()
    enrollments  = Enrollment.query.filter_by(status="Active").all()
    courses      = Course.query.filter_by(is_active=True).all()
    # Utilization per course
    course_util = []
    for c in courses:
        enrolled = Enrollment.query.filter_by(course_id=c.id, status="Active").count()
        util_pct = round(enrolled / c.capacity * 100, 1) if c.capacity else 0
        course_util.append({"course": c, "enrolled": enrolled, "util_pct": util_pct})
    return render_template('scm.html', resources=resources,
                           course_util=course_util, enrollments=enrollments)

# ─────────────────────────────────────────────
# API Endpoints (for charts)
# ─────────────────────────────────────────────
@app.route('/api/stats')
def api_stats():
    students = Student.query.filter_by(is_active=True).all()
    return jsonify({
        "total": len(students),
        "categories": {cat: sum(1 for s in students if s.category == cat)
                       for cat in ["Excellent", "Average", "At Risk", "Invalid"]},
        "avg_marks": round(sum(s.marks for s in students) / len(students), 1) if students else 0,
        "avg_attendance": round(sum(s.attendance for s in students) / len(students), 1) if students else 0,
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Seed demo data if empty
        if Student.query.count() == 0:
            demo = [
                ("Priya Sharma", 88, 92), ("Rahul Mehta", 45, 55),
                ("Anjali Patel", 72, 78), ("Karan Singh", 31, 48),
                ("Sneha Iyer", 95, 97),  ("Amit Gupta", 60, 65),
                ("Pooja Nair", 20, 40),  ("Rohan Das", 79, 85),
            ]
            for name, marks, att in demo:
                cat  = categorize_student(marks, att)
                risk = get_risk_score(marks, att)
                db.session.add(Student(name=name, marks=marks, attendance=att,
                                       category=cat, risk_score=risk,
                                       enrolled_date=datetime.utcnow()))
            # Demo course
            db.session.add(Course(name="Computer Science", code="CS101", credits=4, capacity=60))
            db.session.add(Course(name="Mathematics",      code="MA201", credits=3, capacity=50))
            db.session.add(Resource(title="Python Programming", resource_type="Book", quantity=30, available=22))
            db.session.commit()
            print("Demo data seeded.")
    app.run(debug=True)