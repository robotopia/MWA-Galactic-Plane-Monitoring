from django.urls import re_path, path, include

from . import views

urlpatterns = [
    re_path(r'^(?P<epoch>[EB]poch[0-9]+)$', views.EpochOverviewView, name="epoch_overview"),
    re_path(r'^session_settings$', views.UserSessionSettings, name="user_session_settings"),
    re_path(r'^overview$', views.EpochsView, name="epochs"),
    re_path(r'^find_observation$', views.FindObservation, name="find_observation"),
    re_path(r'^remote_file$', views.RemoteFileView, name="remote_file"),
    re_path(r'^remote_command$', views.RemoteCommandView, name="remote_command"),
    re_path(r'^proc_obs_task/(?P<obs_id>[0-9]+)/(?P<task_id>[0-9]+)$', views.ProcessingObsTaskView, name="proc_obs_task"),
    re_path(r'^set_epoch_cal/(?P<epoch>[EB]poch[0-9]+)$', views.setEpochCal, name="set_epoch_cal"),
    re_path(r'^source_finder$', views.sourceFinder, name="source_finder"),
    re_path(r'^backups/(?P<epoch>[EB]poch[0-9]+)$', views.backupView, name="backup_view"),
    re_path(r'^api/set_qa$', views.changeQaStateView, name="set_qa"),
    path('', include('django.contrib.auth.urls')),
]
