#!/bin/bash

# Выполнить скрипты и затем запустить приложение
python create_all_db
python set_admin_role.py
exec gunicorn run:app