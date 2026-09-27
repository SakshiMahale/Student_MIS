from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Student(db.Model):
    __tablename__ = 'students'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    marks         = db.Column(db.Float, nullable=False)
    attendance    = db.Column(db.Float, nullable=False)
    category      = db.Column(db.String(20))
    risk_score    = db.Column(db.Float, default=0.0)
    email         = db.Column(db.String(120))
    phone         = db.Column(db.String(20))
    enrolled_date = db.Column(db.DateTime, default=datetime.utcnow)
    is_active     = db.Column(db.Boolean, default=True)
    # Relationships
    communications = db.relationship('Communication', backref='student', lazy=True)
    enrollments    = db.relationship('Enrollment',    backref='student', lazy=True)

class Course(db.Model):
    __tablename__ = 'courses'
    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(120), nullable=False)
    code      = db.Column(db.String(20),  nullable=False, unique=True)
    credits   = db.Column(db.Integer, default=3)
    capacity  = db.Column(db.Integer, default=60)
    is_active = db.Column(db.Boolean, default=True)
    enrollments = db.relationship('Enrollment', backref='course', lazy=True)

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id   = db.Column(db.Integer, db.ForeignKey('courses.id'),  nullable=False)
    enrolled_on = db.Column(db.DateTime, default=datetime.utcnow)
    status      = db.Column(db.String(20), default="Active")  # Active / Dropped / Completed

class Communication(db.Model):
    __tablename__ = 'communications'
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    comm_type  = db.Column(db.String(20), default="Email")  # Email / SMS / Notice
    sent_on    = db.Column(db.DateTime, default=datetime.utcnow)
    status     = db.Column(db.String(20), default="Sent")

class Resource(db.Model):
    __tablename__ = 'resources'
    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(150), nullable=False)
    resource_type = db.Column(db.String(40), default="Book")  # Book / Lab / Software / Equipment
    quantity      = db.Column(db.Integer, default=1)
    available     = db.Column(db.Integer, default=1)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id        = db.Column(db.Integer, primary_key=True)
    action    = db.Column(db.String(255), nullable=False)
    module    = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)