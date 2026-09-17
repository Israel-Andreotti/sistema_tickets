import os
import dj_database_url

SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-insegura-so-para-dev')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # logo depois do SecurityMiddleware
    # ...resto do seu MIDDLEWARE existente
]

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DATABASES = {
    'default': dj_database_url.config(default=os.environ.get('DATABASE_URL'))
}
