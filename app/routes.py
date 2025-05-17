from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .forms import RegisterForm, LoginForm, ProfileForm
from .models import User
from . import db
from .email_utils import send_confirmation_email

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
            return redirect(url_for('auth.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)


@auth.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

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
