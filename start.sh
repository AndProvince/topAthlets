#!/bin/bash

# Выполнить скрипты и затем запустить приложение
python create_all_db.py
python set_admin_role.py
exec gunicorn run:app