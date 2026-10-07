"""
URL configuration for core project.

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
from django.conf.urls.static import static
from django.urls import include, path

from core.views import HomeView, StyleguideView

# No Django admin route on purpose (see INSTALLED_APPS / docs/decisions.md):
# the end user configures everything through the app, in prod and in dev alike.
urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('users/', include('users.urls')),
    path('workspace/', include('workspace.urls')),
    path('notes/', include('notes.urls')),
    path('llm/', include('llm.urls')),
    path('sources/', include('sources.urls')),
]

if settings.DEBUG:
    urlpatterns += [path('styleguide/', StyleguideView.as_view(), name='styleguide')]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
