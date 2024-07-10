from django.urls import re_path, path, include

from . import views

urlpatterns = [
    re_path(r'^(?P<pipeline>\w+)/(?P<epoch>Epoch[0-9]+)/(?P<user>\w+)$', views.EpochOverviewView, name="epoch_overview"),
    re_path(r'^overview/(?P<pipeline>\w+)/(?P<user>\w+)$', views.EpochsView, name="epochs"),
    re_path(r'^set_epoch_cal/(?P<epoch>Epoch[0-9]+)/(?P<user>\w+)$', views.setEpochCal, name="set_epoch_cal"),
    re_path(r'^api/set_qa$', views.changeQaStateView, name="set_qa"),
]
