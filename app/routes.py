from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .forms import RegisterForm, LoginForm, ProfileForm, RaceForm
from .models import User, Race
from . import db
from .email_utils import send_confirmation_email
from flask import current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import uuid
from flask import send_from_directory

auth = Blueprint('auth', __name__)

from functools import wraps

# вспомогательный декоратор, если нет ролей
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth.route('/admin/users')
@admin_required
def admin_users():
    email_filter = request.args.get('email', '').strip()
    query = User.query
    if email_filter:
        query = query.filter(User.email.ilike(f"%{email_filter}%"))
    users = query.all()
    return render_template('admin_users.html', users=users)

@auth.route('/admin/users/block/<int:user_id>')
@admin_required
def block_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.active = False
        db.session.commit()
        flash(f'User {user.email} blocked.', 'info')
    return redirect(url_for('auth.admin_users'))

@auth.route('/admin/users/unblock/<int:user_id>')
@admin_required
def unblock_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.active = True
        db.session.commit()
        flash(f'User {user.email} unblocked.', 'info')
    return redirect(url_for('auth.admin_users'))

@auth.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        if user.id == current_user.id:
            flash("Нельзя удалить самого себя.", "warning")
        else:
            db.session.delete(user)
            db.session.commit()
            flash(f"Пользователь {user.email} удалён.", "info")
    return redirect(url_for('auth.admin_users'))

@auth.route('/admin/users/toggle_admin/<int:user_id>')
@admin_required
def toggle_admin(user_id):
    user = User.query.get(user_id)
    if user:
        if user.id == current_user.id:
            flash("Нельзя снять с себя права администратора.", "warning")
        else:
            user.is_admin = not user.is_admin
            db.session.commit()
            status = "назначен админом" if user.is_admin else "снят с админов"
            flash(f"Пользователь {user.email} {status}.", "info")
    return redirect(url_for('auth.admin_users'))


@auth.route('/')
def home():
    return render_template('home.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('auth.register'))
        new_user = User(email=form.email.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        send_confirmation_email(new_user)
        flash('Registration successful. Please check your email to confirm.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)

@auth.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.get(int(token))
    if user:
        user.email_confirmed = True
        db.session.commit()
        flash('Email confirmed!', 'success')
    else:
        flash('Invalid confirmation link.', 'danger')
    return redirect(url_for('auth.login'))

@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if not user.active:
                flash('Ваш аккаунт заблокирован.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('auth.home'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


# @auth.route('/dashboard')
# @login_required
# def dashboard():
#     return render_template('dashboard.html')

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        db.session.commit()
        flash('Profile updated successfully.', 'success')
        return redirect(url_for('auth.profile'))
    return render_template('profile.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/races')
@login_required
def all_races():
    if not current_user.is_admin:
        return redirect(url_for('auth.login'))

    search_name = request.args.get('name', '', type=str)
    query = Race.query

    if search_name:
        query = query.filter(Race.name.ilike(f'%{search_name}%'))

    races = query.order_by(Race.date.desc()).all()
    return render_template('all_races.html', races=races, search_name=search_name)


@auth.route('/races/add', methods=['GET', 'POST'])
@login_required
def add_race():
    if not current_user.is_admin:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        name = request.form['name']
        date_str = request.form['date']
        date = datetime.strptime(date_str, '%Y-%m-%d').date()

        route_file = request.files.get('route_file')
        result_file = request.files.get('result_file')

        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        race = Race(name=name, date=date)

        # Сохраняем маршрут
        if route_file and route_file.filename != '':
            ext = os.path.splitext(route_file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            route_path = os.path.join(upload_folder, unique_name)
            route_file.save(route_path)
            race.route_file = unique_name
            race.route_file_orig = route_file.filename

        # Сохраняем результаты
        if result_file and result_file.filename != '':
            ext = os.path.splitext(result_file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            result_path = os.path.join(upload_folder, unique_name)
            result_file.save(result_path)
            race.result_file = unique_name
            race.result_file_orig = result_file.filename

        db.session.add(race)
        db.session.commit()
        return redirect(url_for('auth.all_races'))

    return render_template('add_race.html')

@auth.route('/races/<int:race_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_race(race_id):
    if not current_user.is_admin:
        return redirect(url_for('auth.login'))

    race = Race.query.get_or_404(race_id)

    if request.method == 'POST':
        race.name = request.form['name']
        date_str = request.form['date']
        race.date = datetime.strptime(date_str, '%Y-%m-%d').date()

        route_file = request.files.get('route_file')
        result_file = request.files.get('result_file')

        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        # Обновляем маршрут, если новый файл
        if route_file and route_file.filename != '':
            ext = os.path.splitext(route_file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            route_path = os.path.join(upload_folder, unique_name)
            route_file.save(route_path)
            race.route_file = unique_name
            race.route_file_orig = route_file.filename

        # Обновляем результаты, если новый файл
        if result_file and result_file.filename != '':
            ext = os.path.splitext(result_file.filename)[1]
            unique_name = f"{uuid.uuid4().hex}{ext}"
            result_path = os.path.join(upload_folder, unique_name)
            result_file.save(result_path)
            race.result_file = unique_name
            race.result_file_orig = result_file.filename

        db.session.commit()
        return redirect(url_for('auth.all_races'))

    return render_template('edit_race.html', race=race)



@auth.route('/races/<int:race_id>/delete', methods=['POST'])
@login_required
def delete_race(race_id):
    if not current_user.is_admin:
        return redirect(url_for('auth.login'))

    race = Race.query.get_or_404(race_id)

    db.session.delete(race)
    db.session.commit()
    flash('Соревнование удалено', 'info')
    return redirect(url_for('auth.all_races'))


@auth.route('/download/<filename>')
@login_required
def download_file(filename):
    original_name = request.args.get('original_name', filename)

    # Путь к папке с файлами
    uploads_dir = current_app.config['UPLOAD_FOLDER']

    # Отдаем файл с оригинальным именем (Content-Disposition)
    return send_from_directory(
        uploads_dir,
        filename,
        as_attachment=True,
        download_name=original_name
    )

