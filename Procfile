release: FLASK_APP=run.py flask db upgrade
web: FLASK_CONFIG=production gunicorn "app:create_app()" --bind 0.0.0.0:$PORT
