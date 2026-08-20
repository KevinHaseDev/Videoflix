#!/bin/sh
# Produktions-Entrypoint. Unterschiede zu backend.entrypoint.sh:
#   - kein makemigrations: Migrationen kommen fertig aus dem Repo
#   - kein Default-Passwort fuer den Superuser; ohne gesetztes Passwort
#     wird kein Account angelegt
#   - gunicorn ohne --reload, dafuer mehrere Worker und laengerer Timeout
#     fuer Video-Uploads

set -e

echo "Warte auf PostgreSQL auf $DB_HOST:$DB_PORT..."
while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; do
  echo "PostgreSQL ist nicht erreichbar - schlafe 1 Sekunde"
  sleep 1
done
echo "PostgreSQL ist bereit - fahre fort..."

python manage.py collectstatic --noinput
python manage.py migrate --noinput

python manage.py shell <<EOF
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if not password:
    print("DJANGO_SUPERUSER_PASSWORD nicht gesetzt - kein Superuser angelegt.")
elif not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created.")
else:
    print(f"Superuser '{username}' already exists.")
EOF

python manage.py rqworker high default &

exec gunicorn core.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --threads 2 \
  --timeout 120
