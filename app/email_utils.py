from flask_mail import Message
from flask import url_for
from . import mail
from threading import Thread
from flask import current_app

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_confirmation_email(user):
    token = str(user.id)  # Можно заменить на безопасный токен
    msg = Message('Confirm Your Email', sender='noreply@example.com', recipients=[user.email])
    link = url_for('auth.confirm_email', token=token, _external=True)
    msg.body = f'Please click the link to confirm your email: {link}'
    Thread(target=send_async_email, args=(current_app._get_current_object(), msg)).start()
