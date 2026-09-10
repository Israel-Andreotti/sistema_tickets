"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from config.views import preview_erro_403, preview_erro_500
from tickets.views import LoginView, confirmar_codigo_view, definir_nova_senha_view, esqueci_senha_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/esqueci-senha/', esqueci_senha_view, name='esqueci_senha'),
    path('accounts/confirmar-codigo/', confirmar_codigo_view, name='confirmar_codigo'),
    path('accounts/nova-senha/', definir_nova_senha_view, name='definir_nova_senha'),
    # Só respondem fora de 404 quando DEBUG=True (checado dentro das views,
    # não aqui) — servem pra pré-visualizar 403.html/500.html sem precisar
    # provocar o erro de verdade.
    path('preview-erro/403/', preview_erro_403, name='preview_erro_403'),
    path('preview-erro/500/', preview_erro_500, name='preview_erro_500'),
    path('tickets/', include('tickets.urls')),
    path('', RedirectView.as_view(pattern_name='tickets:portal', permanent=False)),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
