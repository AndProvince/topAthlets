from . import db
from flask_login import UserMixin
from . import login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email_confirmed = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean(), default=True)
    is_admin = db.Column(db.Boolean, default=False)

    first_name = db.Column(db.String(100), default='')
    last_name = db.Column(db.String(100), default='')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Race(db.Model):
    __bind_key__ = 'races'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, nullable=False)
    route_file = db.Column(db.String(200))  # физическое имя
    route_file_orig = db.Column(db.String(200))  # оригинальное имя
    result_file = db.Column(db.String(200))
    result_file_orig = db.Column(db.String(200))

    user_links = db.relationship('UserRace', backref='race', lazy='dynamic')

    def __repr__(self):
        return f'<Race {self.name}>'

class UserRace(db.Model):
    __bind_key__ = 'races'
    __tablename__ = 'user_races'  # обязательно явно указать имя таблицы
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)  # не ForeignKey, т.к. User в другой БД
    race_id = db.Column(db.Integer, db.ForeignKey('race.id'))

