# """
# WSGI config for subhub project.

# It exposes the WSGI callable as a module-level variable named ``application``.

# For more information on this file, see
# https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
# """




# import os
# import django
# from django.core.wsgi import get_wsgi_application

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'notifications.settings')
# application = get_wsgi_application()

# # 🔥 Run migration and create superuser
# try:
#     django.setup()
#     from django.core.management import call_command
#     from django.contrib.auth import get_user_model

#     # Run migrations
#     call_command('migrate', interactive=False)

#     # Create superuser if not exists
#     User = get_user_model()
#     if not User.objects.filter(username='admin@gmail').exists():
#         User.objects.create_superuser(
#             username='admin@gmail.com',
#             email='admin@gmail.com',
#             password='admin@123'
#         )
#         print("✅ Superuser 'admin' created.")
#     else:
#         print("ℹ️ Superuser 'admin' already exists.")

# except Exception as e:
#     print("❌ Error during startup:", str(e))



"""
WSGI config for incubation project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'subhub.settings')

application = get_wsgi_application()
