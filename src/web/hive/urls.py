from django.urls import path

from . import views

app_name = "hive"
urlpatterns = [
    path("", views.dashboard, name="index"),
]

