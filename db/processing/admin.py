from django.contrib import admin
from .models import *

# Epoch filter
class EpochListFilter(admin.SimpleListFilter):
    title = "epoch"
    parameter_name = "epoch"

    def lookups(self, request, model_admin):
        qs = model_admin.get_queryset(request)

        year = request.GET.get("year")
        if year == '2022':
            qs = qs.filter(obs__gte=1325030418, obs__lte=1356566417)
        elif year == '2024':
            qs = qs.filter(obs__gte=1388102418, obs__lte=1419724817)

        if qs.model.__name__ == 'Observation':
            distinct_epochs = list({observation.epoch.epoch for observation in qs})
        else:
            distinct_epochs = list({obj.obs.epoch.epoch for obj in qs})
        distinct_epochs.sort()
        return [(epoch, epoch) for epoch in distinct_epochs]

    def queryset(self, request, queryset):
        if self.value() is not None:
            min_obsid = int(self.value()[5:])*86400 + 1335398418
            max_obsid = (int(self.value()[5:]) + 1)*86400 + 1335398418 - 1
            return queryset.filter(obs__gte=min_obsid, obs__lt=max_obsid)
        else:
            return queryset

# Year filter
class YearListFilter(admin.SimpleListFilter):
    title = "observation year"
    parameter_name = "year"

    def lookups(self, request, model_admin):
        return [
            ("2022", "2022"),
            ("2024", "2024"),
        ]

    def queryset(self, request, queryset):
        if self.value() == '2022':
            return queryset.filter(obs__gte=1325030418, obs__lte=1356566417)
        elif self.value() == '2024':
            return queryset.filter(obs__gte=1388102418, obs__lte=1419724817)

@admin.register(AntennaFlag)
class AntennaFlagAdmin(admin.ModelAdmin):
    list_display = ['pk', 'start_obs_id', 'end_obs_id', 'antenna']

@admin.register(ApplyCal)
class ApplyCalAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'cal_obs', 'usable']
    autocomplete_fields = ['obs', 'cal_obs']

@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'epoch', 'acacia']
    list_filter = ['epoch']
    autocomplete_fields = ['obs']

@admin.register(CalApparent)
class CalApparentAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'source', 'appflux', 'infov']

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ['name', 'hpc']

@admin.register(Epoch)
class EpochAdmin(admin.ModelAdmin):
    list_display = ['obs', 'epoch', 'approx_datetime']
    list_filter = ['epoch']
    date_hierarchy = 'approx_datetime'

@admin.register(EpochOverview)
class EpochOverviewAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'obs', 'epoch', 'user', 'task', 'submission_time', 'status']
    list_filter = ['user', YearListFilter, 'task', 'status', 'epoch']
    date_hierarchy = 'submission_time'

@admin.register(Hpc)
class HpcAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

@admin.register(HpcUser)
class HpcUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

@admin.register(HpcUserSetting)
class HpcUserSettingAdmin(admin.ModelAdmin):
    list_display = ['id', 'hpc_user', 'account', 'max_array_jobs']

@admin.register(Mosaic)
class MosaicAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'user', 'job_id', 'status']

@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ['obs', 'projectid', 'cal_obs', 'calibration', 'ra_pointing', 'dec_pointing']
    list_filter = ['calibration', YearListFilter, EpochListFilter]
    search_fields = ['obs']

@admin.register(PipelineStep)
class PipelineStepAdmin(admin.ModelAdmin):
    list_display = ['pk', 'pipeline', 'step_order', 'task']

@admin.register(TaskClusterSetting)
class TaskClusterSettingAdmin(admin.ModelAdmin):
    list_display = ['pk', 'task', 'cluster', 'time_request', 'queue']

@admin.register(Processing)
class ProcessingAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'obs_id', 'user', 'task', 'submission_time', 'status']
    list_filter = ['user', 'task', YearListFilter, EpochListFilter]

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['source', 'raj2000', 'decj2000', 'flux', 'alpha', 'beta']

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['pk', 'name', 'script_name']


