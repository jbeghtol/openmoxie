from django.urls import path

from . import views

app_name = "hive"
urlpatterns = [
    path("", views.root_view, name="root"),
    path("setup", views.SetupView.as_view(), name="setup"),
    path('hive_configure/', views.hive_configure, name='hive_configure'),
    path("dashboard", views.DashboardView.as_view(), name="dashboard"),
    path('dashboard/<str:alert_message>/', views.DashboardView.as_view(), name='dashboard_alert'),
    path("interact/<int:pk>", views.InteractionView.as_view(), name="interact"),
    path("interact_update", views.interact_update, name="interact_update"),
    path("reload_database", views.reload_database, name="reload_database"),
    path('endpoint/', views.endpoint_qr, name='endpoint_qr'),
    path('wifi_edit/', views.WifiQREditView.as_view(), name='wifi_edit'),
    path('wifi_qr/', views.wifi_qr, name='wifi_qr'),
    path("moxie/<int:pk>", views.MoxieView.as_view(), name="moxie"),
    path("moxie_data/<int:pk>", views.MoxieDataView.as_view(), name="moxie_data"),
    path("moxie_missions/<int:pk>", views.MoxieMissionsView.as_view(), name="moxie_missions"),
    path("mission_edit/<int:pk>", views.mission_edit, name="mission_edit"),
    path("face/<int:pk>", views.MoxieFaceView.as_view(), name="face"),
    path("face_edit/<int:pk>", views.face_edit, name="face_edit"),
    path("moxie_edit/<int:pk>", views.moxie_edit, name="moxie_edit"),
    path("moxie_wake/<int:pk>", views.moxie_wake, name="moxie_wake"),
    path("puppet/<int:pk>", views.MoxiePuppetView.as_view(), name="puppet"),
    path("puppet_api/<int:pk>", views.puppet_api, name="puppet_api"),
    path("export_content/", views.ExportDataView.as_view(), name="export_content"),
    path("export_data/", views.export_data, name="export_data"),
    path("import_review/", views.upload_import_data, name="import_review"),
    path("import_data/", views.import_data, name="import_data"),
]
