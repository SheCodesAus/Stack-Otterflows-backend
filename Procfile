release: python manage.py migrate
web: gunicorn --pythonpath backend backend.wsgi --log-file -