from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("healthz", views.healthz, name="healthz"),
    path("access-denied/", views.access_denied, name="access_denied"),
    path("logged-out/", views.logged_out, name="logged_out"),
    path("settings/", views.app_settings, name="settings"),
]
