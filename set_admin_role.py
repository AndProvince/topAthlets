from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    email = 'admin@example.com'
    password = 'adminpassword'

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, email_confirmed=True, active=True, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        print(f'Создан новый админ: {email}')
    else:
        user.is_admin = True
        user.active = True
        print(f'Пользователь {email} обновлён до администратора')

    db.session.commit()
