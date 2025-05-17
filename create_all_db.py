from app import create_app, db
from app.models import User, Race  # импортируем модели, чтобы они зарегистрировались

app = create_app()

with app.app_context():
    # Создание таблиц в основной базе данных (например, users.db)
    db.create_all()
    print("База данных пользователей успешно создана.")
    print("База данных соревнований успешно создана.")
