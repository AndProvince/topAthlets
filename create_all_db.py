from app import create_app, db

app = create_app()

with app.app_context():
    db.create_all()  # создает таблицы из users.db
    # db.create_all(bind='races')  # создает Race, Discipline, UserRace
    print("Базы данных созданы.")