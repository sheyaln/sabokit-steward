from django.urls import path

from . import views

app_name = "members"

urlpatterns = [
    path("", views.member_list, name="list"),
    path("new/", views.member_create, name="create"),
    path("<int:pk>/", views.member_detail, name="detail"),
    path("<int:pk>/edit/", views.member_edit, name="edit"),
    path("<int:pk>/activate/", views.member_activate, name="activate"),
    path("<int:pk>/deactivate/", views.member_deactivate, name="deactivate"),
    path("<int:pk>/groups/add/", views.member_add_group, name="add_group"),
    path("<int:pk>/groups/remove/", views.member_remove_group, name="remove_group"),
    path(
        "<int:pk>/password-reset/",
        views.member_password_reset,
        name="password_reset",
    ),
    path("<int:pk>/mfa/remove/", views.member_remove_mfa, name="remove_mfa"),
]
