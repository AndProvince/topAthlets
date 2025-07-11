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

    result_file = db.Column(db.String(200))  # Сохранённое имя результатов
    result_file_orig = db.Column(db.String(200))  # Оригинальное имя результатовs

    disciplines = db.relationship('Discipline', backref='race', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Race {self.name}>'


class Discipline(db.Model):
    __bind_key__ = 'races'
    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(db.Integer, db.ForeignKey('race.id', ondelete='CASCADE'), nullable=False)

    name = db.Column(db.String(150), nullable=False)

    route_file = db.Column(db.String(200))  # Сохранённое имя GPX
    route_file_orig = db.Column(db.String(200))  # Оригинальное имя GPX

    result_file = db.Column(db.String(200))  # Сохранённое имя результатов
    result_file_orig = db.Column(db.String(200))  # Оригинальное имя результатов
    participants_count = db.Column(db.Integer)  # Количество кругов

    difficulty_coefficient = db.Column(db.Float)  # Коэффициент сложности (рассчитываемый)

    laps = db.Column(db.Integer)  # Количество кругов
    ascent_difficulty_percent = db.Column(db.Integer)  # % сложных подъёмов
    descent_difficulty_percent = db.Column(db.Integer)  # % сложных спусков
    weather_condition = db.Column(db.String(50))

    user_links = db.relationship(
        'UserDiscipline',
        backref='discipline',
        lazy='dynamic',
        cascade='all, delete-orphan')

    participants = db.relationship(
        'Participant',
        backref='discipline',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def __repr__(self):
        return f'<Discipline {self.name} (Race ID: {self.race_id})>'


# Связь пользователь ↔ дисциплина (в races.db)
class UserDiscipline(db.Model):
    __bind_key__ = 'races'
    __tablename__ = 'user_discipline'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)  # User в другой БД
    discipline_id = db.Column(db.Integer, db.ForeignKey('discipline.id'))

    def __repr__(self):
        return f'<UserDiscipline user_id={self.user_id}, discipline_id={self.discipline_id}>'


class Participant(db.Model):
    __bind_key__ = 'races'
    id = db.Column(db.Integer, primary_key=True)

    discipline_id = db.Column(db.Integer, db.ForeignKey('discipline.id', ondelete='CASCADE'), nullable=False)

    index = db.Column(db.Integer)  # порядковый номер в таблице
    name = db.Column(db.String(150), nullable=False)
    numder = db.Column(db.String(50))  # возможно, это номер участника
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))

    pace = db.Column(db.String(50))  # средний темп, строка (например, "5:15")
    time = db.Column(db.String(50))  # финишное время, строка (например, "1:03:22")

    point = db.Column(db.Integer, default=0)  # очки за дистанцию

    def __repr__(self):
        return f"<Participant {self.name} (#{self.numder})>"

