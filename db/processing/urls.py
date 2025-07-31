from django.urls import re_path, path, include

from . import views

urlpatterns = [
    re_path(r'^(?P<epoch>[EB]poch[0-9]+)$', views.EpochOverviewView, name="epoch_overview"),
    re_path(r'^session_settings$', views.UserSessionSettings, name="user_session_settings"),
    re_path(r'^overview$', views.EpochsView, name="epochs"),
    re_path(r'^set_epoch_cal/(?P<epoch>[EB]poch[0-9]+)$', views.setEpochCal, name="set_epoch_cal"),
    re_path(r'^source_finder$', views.sourceFinder, name="source_finder"),
    re_path(r'^backups/(?P<epoch>[EB]poch[0-9]+)$', views.backupView, name="backup_view"),
    re_path(r'^api/set_qa$', views.changeQaStateView, name="set_qa"),
    path('', include('django.contrib.auth.urls')),
]
