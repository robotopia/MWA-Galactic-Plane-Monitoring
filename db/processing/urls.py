from django.urls import re_path, path, include

from . import views

urlpatterns = [
    re_path(r'^(?P<epoch>[EB]poch[0-9]+)$', views.EpochOverviewView, name="epoch_overview"),
    re_path(r'^session_settings$', views.UserSessionSettings, name="user_session_settings"),
    re_path(r'^hpc_user_settings/(?P<hpc_user_id>[0-9]+)$', views.HpcUserSettingsView, name="hpc_user_settings"),
    re_path(r'^overview$', views.EpochsView, name="epochs"),
    re_path(r'^find_observation$', views.FindObservation, name="find_observation"),
    re_path(r'^log/(?P<processing_id>[0-9]+)/(?P<logfile_type>\w+)$', views.LogView, name="log_view"),
    re_path(r'^proc_obs_task/(?P<obs_id>[0-9]+)/(?P<task_id>[0-9]+)$', views.ProcessingObsTaskView, name="proc_obs_task"),
    re_path(r'^set_epoch_cal/(?P<epoch>[EB]poch[0-9]+)$', views.setEpochCal, name="set_epoch_cal"),
    re_path(r'^source_finder$', views.sourceFinder, name="source_finder"),
    re_path(r'^add_observations_to_semester_plan$', views.add_observations_to_semester_plan, name="add_observations_to_semester_plan"),
    re_path(r'^backups/(?P<epoch>[EB]poch[0-9]+)$', views.backupView, name="backup_view"),
    re_path(r'^api/set_qa$', views.changeQaStateView, name="set_qa"),
    re_path(r'^hpc_login$', views.HPCLogin, name='hpc_login'),

    re_path(f'^api/load_profile$', views.load_profile, name="load_profile"),
    re_path(f'^api/load_job_environment$', views.load_job_environment, name="load_job_environment"),
    re_path(f'^api/create_processing_job$', views.create_processing_job, name="create_processing_job"),
    re_path(f'^api/update_processing_job_status$', views.update_processing_job_status, name="update_processing_job_status"),
    re_path(f'^api/get_datadir$', views.get_datadir, name="get_datadir"),
    re_path(f'^api/get_acacia_path$', views.get_acacia_path, name="get_acacia_path"),
    re_path(f'^api/save_acacia_path$', views.save_acacia_path, name="save_acacia_path"),
    re_path(f'^api/get_antennaflags$', views.get_antennaflags, name="get_antennaflags"),
    re_path(f'^api/get_template$', views.get_template, name="get_template"),
    re_path(f'^api/get_calfile$', views.get_calfile, name="get_calfile"),
    re_path(f'^api/update_job_id$', views.update_job_id, name="update_job_id"),
    path('', include('django.contrib.auth.urls')),
]
