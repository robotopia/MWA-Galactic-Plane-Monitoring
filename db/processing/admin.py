from django.contrib import admin
from .models import *
from astropy.time import Time
from django.db.models import Min, Max

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
        result = Observation.objects.aggregate(Min('obs'), Max('obs'))
        min_year = Time(result['obs__min'], format='gps', scale='utc').datetime.year
        max_year = Time(result['obs__max'], format='gps', scale='utc').datetime.year
        return [(str(year), str(year)) for year in range(min_year, max_year+1)]

    def queryset(self, request, queryset):
        if self.value() is not None:
            year_start = Time(f'{self.value()}-01-01 00:00:00', scale='utc', format='iso')
            year_end   = Time(f'{self.value()}-12-31 23:59:59', scale='utc', format='iso')
            return queryset.filter(obs__gte=year_start.gps, obs__lte=year_end.gps)

@admin.register(ArrayJob)
class ArrayJobAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'processing__job_id', 'processing__pipeline_step', 'processing__cluster', 'start_time', 'status']
    list_filter = ['status', YearListFilter]
    autocomplete_fields = ['obs', 'cal_obs']
    search_fields = ['obs']

@admin.register(AntennaFlag)
class AntennaFlagAdmin(admin.ModelAdmin):
    list_display = ['pk', 'start_obs_id', 'end_obs_id', 'antenna']

@admin.register(ApplyCal)
class ApplyCalAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'cal_obs', 'usable']
    autocomplete_fields = ['obs', 'cal_obs']

@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'obstype', 'epoch', 'acacia', 'tar_contains_folder']
    list_filter = ['epoch', 'obstype']
    autocomplete_fields = ['obs']

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ['name', 'hpc']

@admin.register(Detection)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ['id', 'source', 'obs', 'detection']
    autocomplete_fields = ['obs']

@admin.register(Epoch)
class EpochAdmin(admin.ModelAdmin):
    list_display = ['obs', 'epoch', 'approx_datetime']
    list_filter = ['epoch']
    date_hierarchy = 'approx_datetime'

@admin.register(EpochOverview)
class EpochOverviewAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'obs', 'epoch', 'hpc_user', 'task', 'status']
    list_filter = ['hpc_user', YearListFilter, 'task', 'status', 'epoch']

@admin.register(Hpc)
class HpcAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

@admin.register(HpcPath)
class HpcPathAdmin(admin.ModelAdmin):
    list_display = ['id', 'owner', 'path']
    list_filter = ['owner__hpc', 'owner']

@admin.register(HpcUser)
class HpcUserAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']

@admin.register(HpcUserSetting)
class HpcUserSettingAdmin(admin.ModelAdmin):
    list_display = ['id', 'hpc_user', 'account', 'max_array_jobs']

@admin.register(Lightcurve)
class LightcurveAdmin(admin.ModelAdmin):
    list_display = ['pk', 'source', 'obs', 'flux_Jy', 'flux_Jy_err']

@admin.register(Mosaic)
class MosaicAdmin(admin.ModelAdmin):
    list_display = ['pk', 'obs', 'user', 'job_id', 'status']

@admin.register(Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ['obs', 'projectid', 'cal_obs', 'calibration', 'ra_pointing', 'dec_pointing']
    list_filter = ['calibration', YearListFilter, EpochListFilter]
    search_fields = ['obs']

@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ['pk', 'name']

@admin.register(PipelineStep)
class PipelineStepAdmin(admin.ModelAdmin):
    list_display = ['pk', 'pipeline', 'step_order', 'task']

@admin.register(TaskClusterSetting)
class TaskClusterSettingAdmin(admin.ModelAdmin):
    list_display = ['pk', 'task', 'cluster', 'time_request', 'queue']
    list_filter = ['task', 'cluster']

@admin.register(Processing)
class ProcessingAdmin(admin.ModelAdmin):
    list_display = ['pk', 'job_id', 'hpc_user', 'pipeline_step']
    list_filter = ['hpc_user', 'pipeline_step']

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ['pk', 'name']

@admin.register(SemesterPlan)
class SemesterPlanAdmin(admin.ModelAdmin):
    list_display = ['pk', 'semester', 'obs', 'pipeline']
    list_filter = ['semester', 'pipeline']
    search_fields = ['obs__obs']
    autocomplete_fields = ['obs']

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'raj2000', 'decj2000']

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['pk', 'name', 'script_name']

@admin.register(UserSessionSetting)
class UserSessionSettingAdmin(admin.ModelAdmin):
    list_display = ['pk', 'user', 'selected_hpc_user', 'selected_semester', 'selected_pipeline']
    list_filter = ['user', 'selected_hpc_user', 'selected_semester']

@admin.register(SlurmSettings)
class SlurmSettingAdmin(admin.ModelAdmin):
    list_display = ['pk', 'pipeline_step', 'cluster']
    list_filter = ['pipeline_step', 'cluster']

