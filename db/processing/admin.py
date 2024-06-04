from django.contrib import admin
from .models import *

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
    list_display = ['obs_id', 'projectid', 'cal_obs', 'status']

@admin.register(PipelineStep)
class PipelineStepAdmin(admin.ModelAdmin):
    list_display = ['pk', 'pipeline', 'step_order', 'task']

@admin.register(Processing)
class ProcessingAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'obs', 'user', 'task', 'submission_time', 'status']
    list_filter = ['user']

@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ['source', 'raj2000', 'decj2000', 'flux', 'alpha', 'beta']


