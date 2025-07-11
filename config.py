import os
from dotenv import load_dotenv
load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///users.db'
    SQLALCHEMY_BINDS = {
        'races': 'sqlite:///races.db'  # вторая БД — соревнования
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    # ROUTE_FOLDER = os.path.join(UPLOAD_FOLDER, 'routes')
    RESULTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'results')

    ALLOWED_EXTENSIONS = {'gpx', 'csv'}

    BASE_POINT = 1000
    APLHA = 0.65
    BETA = 0.1

