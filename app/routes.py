from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from .forms import RegisterForm, LoginForm, ProfileForm, RaceForm
from .models import User, Race, Discipline, UserDiscipline, Participant
from . import db
from .email_utils import send_confirmation_email
from flask import current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import uuid
from flask import send_from_directory
from sqlalchemy.orm import joinedload
from .utils_clax import parse_clax_and_create_disciplines
from .utils_ranking import get_ranking
import gpxpy

auth = Blueprint('auth', __name__)

from functools import wraps

# вспомогательный декоратор, если нет ролей
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Доступ запрещен', 'danger')
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
        flash(f'Пользователь {user.email} заблокирован', 'info')
    return redirect(url_for('auth.admin_users'))

@auth.route('/admin/users/unblock/<int:user_id>')
@admin_required
def unblock_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.active = True
        db.session.commit()
        flash(f'Пользователь {user.email} разблокирован', 'info')
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
    races = Race.query.order_by(Race.date.desc()).all()
    return render_template('home.html', races=races)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('auth.register'))
        new_user = User(email=form.email.data)
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        send_confirmation_email(new_user)
        flash('Успешная регистрация. Проверьте email для подтверждения', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)

@auth.route('/confirm/<token>')
def confirm_email(token):
    user = User.query.get(int(token))
    if user:
        user.email_confirmed = True
        db.session.commit()
        flash('Email подтвержден', 'success')
    else:
        flash('Некорректная ссылка подтверждения', 'danger')
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
            flash('Успешный вход', 'success')
            return redirect(url_for('auth.home'))
        else:
            flash('Некорректный логин или пароль', 'danger')
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
        flash('Профиль успешно обновлен', 'success')
        return redirect(url_for('auth.profile'))

    # Получаем все соревнования, в которых участвовал текущий пользователь
    # user_races = (
    #     UserDiscipline.query
    #     .filter_by(user_id=current_user.id)
    #     .options(joinedload(UserDiscipline.discipline_id))
    #     .all()
    # )

    # races = [ur.race for ur in user_races if ur.race is not None]
    races = []

    return render_template('profile.html', form=form, races=races)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Успешный выход', 'info')
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

    form = RaceForm()
    if form.validate_on_submit():
        name = form.name.data
        date = form.date.data

        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)

        race = Race(name=name, date=date)

        # Сохраняем clax файл
        clax_file = form.clax_file.data
        if clax_file:
            ext = os.path.splitext(clax_file.filename)[-1].lower()
            if ext != ".clax":
                flash("Можно загружать только .clax файлы", "danger")
                return render_template("edit_race.html", form=form, title="Редактировать соревнование")

            unique_filename = f"{uuid.uuid4().hex}{ext}"
            race.result_file = unique_filename
            race.result_file_orig = clax_file.filename
            clax_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))

        db.session.add(race)
        db.session.commit()
        flash("Соревнование добавлено", "success")
        return redirect(url_for('auth.all_races'))

    return render_template("edit_race.html", form=form, title="Добавить соревнование")

@auth.route('/races/<int:race_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_race(race_id):
    if not current_user.is_admin:
        return redirect(url_for('auth.login'))

    race = Race.query.get_or_404(race_id)

    form = RaceForm(obj=race)

    if form.validate_on_submit():
        race.name = form.name.data
        race.date = form.date.data

        clax_file = form.clax_file.data
        if clax_file:
            ext = os.path.splitext(clax_file.filename)[-1].lower()
            if ext != ".clax":
                flash("Можно загружать только .clax файлы", "danger")
                return render_template("edit_race.html", form=form, title="Редактировать соревнование")

            # Удаляем старый файл при замене (опционально)
            if race.result_file:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], race.result_file))
                except FileNotFoundError:
                    pass

            # Сохраняем новый файл
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            race.result_file = unique_filename
            race.result_file_orig = clax_file.filename
            clax_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))

        db.session.commit()
        flash("Соревнование обновлено", "success")
        return redirect(url_for('auth.all_races'))

    return render_template("edit_race.html", form=form, title="Редактировать соревнование", race=race)



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


@auth.route('/download/<path:filename>')
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

@auth.route('/races/<int:race_id>', methods=['GET', 'POST'])
@login_required
def race_detail(race_id):
    if not current_user.is_admin:
        flash(f'Доступ только для администраторов', 'warning')
        return redirect(url_for('auth.home'))

    race = Race.query.get_or_404(race_id)

    disciplines = Discipline.query.filter_by(race_id=race.id).all()
    parsed = False

    if request.method == 'POST' and 'analyze_clax' in request.form:
        if not race.result_file:
            flash("Для анализа необходимо загрузить clax-файл.", "warning")
        else:
            # Вызов функции для разбора clax-файла
            clax_path = os.path.join(current_app.config['UPLOAD_FOLDER'], race.result_file)
            try:
                parsed = parse_clax_and_create_disciplines(clax_path, race)
                flash("Файл успешно проанализирован.", "success")
            except Exception as e:
                flash(f"Ошибка анализа файла: {e}", "danger")

        return redirect(url_for('auth.race_detail', race_id=race.id))

    return render_template(
        'race_detail.html',
        race=race,
        disciplines=disciplines,
        parsed=parsed
    )


@auth.route('/discipline/<int:discipline_id>/upload_gpx', methods=['POST'])
@login_required
def upload_gpx(discipline_id):
    if not current_user.is_admin:
        flash(f'Доступ только для администраторов', 'warning')
        return redirect(url_for('auth.home'))

    discipline = Discipline.query.get_or_404(discipline_id)

    if 'gpx_file' not in request.files:
        flash("Файл не был загружен", "danger")
        return redirect(url_for('auth.race_detail', race_id=discipline.race_id))

    file = request.files['gpx_file']

    if file.filename == '':
        flash("Имя файла отсутствует", "warning")
        return redirect(url_for('auth.race_detail', race_id=discipline.race_id))

    if not file.filename.lower().endswith('.gpx'):
        flash("Допустимы только GPX-файлы", "danger")
        return redirect(url_for('auth.race_detail', race_id=discipline.race_id))

    try:
        ext = os.path.splitext(file.filename)[-1]
        unique_name = f"{uuid.uuid4().hex}{ext}"

        gpx_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'gpx', str(discipline.race_id))
        os.makedirs(gpx_folder, exist_ok=True)

        file_path = os.path.join(gpx_folder, unique_name)
        file.save(file_path)

        # сохраняем в дисциплину
        discipline.route_file = "gpx/" + str(discipline.race_id) + "/" + unique_name
        discipline.route_file_orig = file.filename

        # очищаем значение коэффицента сложности
        discipline.difficulty_coefficient = 0

        db.session.commit()

        flash("GPX файл успешно загружен", "success")

    except Exception as e:
        flash(f"Ошибка загрузки файла: {str(e)}", "danger")

    return redirect(url_for('auth.race_detail', race_id=discipline.race_id))


@auth.route('/discipline/<int:discipline_id>/delete', methods=['POST'])
@login_required
def delete_discipline(discipline_id):
    if not current_user.is_admin:
        flash(f'Доступ только для администраторов', 'warning')
        return redirect(url_for('auth.home'))

    discipline = Discipline.query.get_or_404(discipline_id)

    race_id = discipline.race_id

    # Только администратор может удалять дисциплины
    if not current_user.is_admin:
        flash("У вас нет прав для удаления дисциплины.", "danger")
        return redirect(url_for('auth.race_detail', race_id=race_id))

    try:
        # Удаляем связанные файлы, если есть
        # if discipline.route_file:
        #     gpx_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'gpx', str(race_id))
        #     file_path = os.path.join(gpx_folder, discipline.route_file)
        #     if os.path.exists(file_path):
        #         os.remove(file_path)
        #
        # if discipline.result_file:
        #     results_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'results', str(race_id))
        #     file_path = os.path.join(results_folder, discipline.result_file)
        #     if os.path.exists(file_path):
        #         os.remove(file_path)

        # Удаляем дисциплину из базы
        db.session.delete(discipline)
        db.session.commit()
        flash("Дистанция успешно удалена.", "success")

    except Exception as e:
        flash(f"Ошибка при удалении: {str(e)}", "danger")

    return redirect(url_for('auth.race_detail', race_id=race_id))

@auth.route('/disciplines/<int:discipline_id>/participants')
@login_required
def view_participants(discipline_id):
    discipline = Discipline.query.get_or_404(discipline_id)
    participants = Participant.query.filter_by(discipline_id=discipline.id).order_by(Participant.index).all()
    return render_template('participants.html', discipline=discipline, participants=participants)


@auth.route('/disciplines/<int:discipline_id>/calculate', methods=['POST'])
@login_required
def calculate_difficulty(discipline_id):
    if not current_user.is_admin:
        flash(f'Доступ только для администраторов', 'warning')
        return redirect(url_for('auth.home'))

    from .utils_RacePoints import calculate_K

    discipline = Discipline.query.get_or_404(discipline_id)

    # Получение данных из формы
    try:
        laps = int(request.form.get('laps', 1))
        ascent_difficulty = float(request.form.get('ascent_difficulty', 0))
        descent_difficulty = float(request.form.get('descent_difficulty', 0))
        weather_condition = request.form.get('weather_condition', 'normal')
    except ValueError:
        flash('Ошибка в введённых данных. Проверьте значения процентов.', 'danger')
        return redirect(request.referrer or url_for('auth.race_detail', race_id=discipline.race_id))

    # Алгоритм вычисления коэффициента сложности
    if discipline.route_file:
        route_file = os.path.join(current_app.config['UPLOAD_FOLDER'], discipline.route_file)

        gpx = gpxpy.parse(open(route_file, 'r'))
        elevation_gain_uphill = gpx.get_uphill_downhill().uphill
        elevation_gain_downhill = gpx.get_uphill_downhill().downhill
        distance = gpx.get_points_data()[-1].distance_from_start

        # TODO добавить расчет среднего рейтинга участников
        avg_rating = 500

        K_final, K_base, C_weather, C_comp = calculate_K(
            distance, elevation_gain_uphill, elevation_gain_downhill, laps,
            ascent_difficulty, descent_difficulty, weather_condition, avg_rating, discipline.participants_count
        )
    else:
        K_final = 1

    k = round(K_final, 2)

    # Сохраняем в БД
    discipline.laps = laps
    discipline.ascent_difficulty_percent = ascent_difficulty
    discipline.descent_difficulty_percent = descent_difficulty
    discipline.weather_condition = weather_condition
    discipline.difficulty_coefficient = k

    db.session.commit()

    flash(f'Коэффициент сложности для {discipline.name} рассчитан: K = {k}', 'success')
    return redirect(url_for('auth.race_detail', race_id=discipline.race_id))


@auth.route('/disciplines/<int:discipline_id>/assign_points', methods=['POST'])
@login_required
def assign_points(discipline_id):
    if not current_user.is_admin:
        flash(f'Доступ только для администраторов', 'warning')
        return redirect(url_for('auth.home'))

    from .utils_RacePoints import get_sec

    discipline = Discipline.query.get_or_404(discipline_id)

    if not discipline.difficulty_coefficient:
        flash('Сначала рассчитайте коэффициент сложности маршрута.', 'warning')
        return redirect(request.referrer or url_for('auth.race_detail', race_id=discipline.race_id))

    # Получаем участников
    participants = discipline.participants

    # Пример начисления очков — от обратного финишного времени
    sorted_participants = sorted(participants, key=lambda p: p.index)
    leader_time = get_sec(sorted_participants[0].time)

    base_points = current_app.config['BASE_POINT']
    alpha = current_app.config['APLHA']
    beta = current_app.config['BETA']

    for place, participant in enumerate(sorted_participants, start=1):
        if participant.time == "DNF":
            participant.point = 0
            # print(participant.name, 0)
        else:
            ratio =  leader_time / get_sec(participant.time)
            ratio = min(ratio, 1 / ratio)
            place_coeff = 1 / (1 + beta * (place - 1))
            participant.point = int(base_points * discipline.difficulty_coefficient * (ratio ** alpha) * place_coeff)
            # print(participant.name, participant.time, round(base_points * discipline.difficulty_coefficient * (ratio ** alpha), 2), participant.point)

    db.session.commit()
    flash(f'Очки начислены участникам дисциплины "{discipline.name}".', 'success')
    return redirect(url_for('auth.race_detail', race_id=discipline.race_id))

@auth.route('/ranking', methods=['GET', 'POST'])
def ranking():
    search_query = request.args.get('q', '').strip()

    ranking, period_start, period_end = get_ranking(search_query)

    return render_template('ranking.html',
                           ranking=ranking,
                           period_start=period_start,
                           period_end=period_end,
                           search_query=search_query
                           )

# @auth.route('/races/<int:race_id>/join', methods=['POST'])
# @login_required
# def join_race(race_id):
#     race = Race.query.get_or_404(race_id)
#
#     # Проверяем, не добавлен ли пользователь уже
#     exists = UserRace.query.filter_by(race_id=race_id, user_id=current_user.id).first()
#     if exists:
#         flash('Вы уже зарегистрированы на это соревнование.', 'info')
#     else:
#         new_link = UserRace(user_id=current_user.id, race_id=race_id)
#         db.session.add(new_link)
#         db.session.commit()
#         flash('Вы успешно зарегистрированы на соревнование!', 'success')
#
#     return redirect(url_for('auth.race_detail', race_id=race_id))

