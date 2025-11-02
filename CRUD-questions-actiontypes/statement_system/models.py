from flask_login import UserMixin
from datetime import datetime
from statement_system import db, login_manager
from datetime import date

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(user_id)

class Statements(db.Model):
    __tablename__ = 'statements'
    statement_number = db.Column(db.Integer, primary_key=True, autoincrement=True)
    choice_number = db.Column(db.Integer, nullable=False)
    choice_text = db.Column(db.Text, nullable=False)
    choice_result = db.Column(db.Text, nullable=False)
    group_id = db.Column(db.Integer, nullable=True)


class StudentAnswers(db.Model):
    __tablename__ = 'student_answers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_number = db.Column(db.Integer, db.ForeignKey('students.student_number'), nullable=False)
    statement_number = db.Column(db.Integer, db.ForeignKey('statements.statement_number'), nullable=False)
    answer_group_id = db.Column(db.Integer, nullable=True)
    answer_choice = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=True)
    answer_result = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    student = db.relationship("Students", backref="answers")
    statement = db.relationship("Statements", backref="answers")

class Students(db.Model):
    __tablename__ = 'students'
    student_number = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_name = db.Column(db.Text, nullable=False)
    student_class = db.Column(db.Text, nullable=False)
    question_status = db.Column(db.Text, nullable=False, default="Not Submitted")
    date_filled = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    action_type = db.Column(db.Text, nullable=False, default="None")
    team = db.Column(db.Text, nullable=True)



class Admin(db.Model, UserMixin):
    __tablename__ = 'admin'
    admin_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.Text, nullable=False)
    password = db.Column(db.String, nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def get_id(self):
        return self.admin_id