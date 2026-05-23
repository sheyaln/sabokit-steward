from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("members/", include("members.urls")),
    path("imports/", include("imports.urls")),
    path("audit/", include("audit.urls")),
    path("", include("core.urls")),
]
