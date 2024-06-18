from django.urls import re_path, path, include

from . import views

urlpatterns = [
    re_path(r'^(?P<epoch>Epoch[0-9]+)/(?P<user>\w+)$', views.EpochOverviewView, name="epoch_overview"),
    re_path(r'^api/set_qa$', views.changeQaStateView, name="set_qa"),
]
