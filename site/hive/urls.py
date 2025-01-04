from django.urls import path

from . import views

app_name = "hive"
urlpatterns = [
    path("", views.root_view, name="root"),
    path("setup", views.SetupView.as_view(), name="setup"),
    path('hive_configure/', views.hive_configure, name='hive_configure'),
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),
    path("interact/<int:pk>", views.InteractionView.as_view(), name="interact"),
    path("interact_update", views.interact_update, name="interact_update"),
    path("reload_database", views.reload_database, name="reload_database"),
    path('endpoint/', views.endpoint_qr, name='endpoint_qr'),
    path("moxie/<int:pk>", views.MoxieView.as_view(), name="moxie"),
    path("moxie_edit/<int:pk>", views.moxie_edit, name="moxie_edit"),
]
