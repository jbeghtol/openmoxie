from django.urls import path

from . import views

app_name = "hive"
urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("interact/<int:pk>", views.InteractionView.as_view(), name="interact"),
    path("interact_update", views.interact_update, name="interact_update"),
    path("reload_database", views.reload_database, name="reload_database"),
]
