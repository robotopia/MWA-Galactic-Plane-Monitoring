from django.contrib import admin
from .models import *

# Epoch filter
class EpochListFilter(admin.SimpleListFilter):
    title = "epoch"
    parameter_name = "epoch"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)
        query_attrs = dict([(param, val) for param, val in request.GET.items()])
        qs = qs.filter(**query_attrs)
        if qs.model.__name__ == 'Observation':
            distinct_epochs = {observation.epoch for observation in qs}
            return [(epoch, epoch) for epoch in distinct_epochs]

    def queryset(self, request, queryset):
        if self.value() is not None:
            min_obsid = int(self.value[4:])*86400 + 1335398418
            max_obsid = (int(self.value[4:]) + 1)*86400 + 1335398418 - 1
            return queryset.filter(obs__gte=min_obsid, obs__lt=max_obsid)
        else:
            return queryset

# Register your models here.
@admin.register(AcaciaFile)
class AcaciaFileAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'type', 'path']

@admin.register(AntennaFlag)
class AntennaFlagAdmin(admin.ModelAdmin):
    list_display = ['pk', 'start_obs_id', 'end_obs_id', 'antenna']

@admin.register(ApplyCal)
class ApplyCalAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'cal_obs', 'usable']

@admin.register(CalApparent)
class CalApparentAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'source', 'appflux', 'infov']

@admin.register(Mosaic)
class MosaicAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'user', 'job_id', 'status']

@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ['obs', 'projectid', 'epoch', 'cal_obs', 'status']
    list_filter = [EpochListFilter]

@admin.register(PipelineStep)
class PipelineStepAdmin(admin.ModelAdmin):
    list_display = ['pk', 'pipeline', 'step_order', 'task']

@admin.register(Processing)
class ProcessingAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'obs_id', 'user', 'task', 'submission_time', 'status']
    list_filter = ['user']

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['source', 'raj2000', 'decj2000', 'flux', 'alpha', 'beta']


