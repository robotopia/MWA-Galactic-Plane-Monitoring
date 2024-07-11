# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AntennaFlag(models.Model):
    start_obs_id = models.IntegerField()
    end_obs_id = models.IntegerField()
    antenna = models.IntegerField()
    notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'antennaflag'


class ApplyCal(models.Model):
    obs = models.ForeignKey('Observation', models.DO_NOTHING)
    cal_obs = models.ForeignKey('Observation', models.DO_NOTHING, related_name='applycal_cal_obs_set')
    usable = models.BooleanField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"obs: {self.obs}, cal: {self.cal_obs}"

    class Meta:
        managed = False
        db_table = 'apply_cal'
        unique_together = (('obs', 'cal_obs'),)
        ordering = ['obs', 'cal_obs']


class Backup(models.Model):
    obs = models.OneToOneField('Observation', models.DO_NOTHING, primary_key=True)
    epoch = models.CharField(max_length=9)
    acacia = models.TextField()

    class Meta:
        managed = False
        db_table = 'backup'
        ordering = ['obs']


class CalApparent(models.Model):
    obs = models.OneToOneField('Observation', models.DO_NOTHING, primary_key=True)  # The composite primary key (obs_id, source) found, that is not supported. The first column is selected.
    source = models.ForeignKey('Source', models.DO_NOTHING, db_column='source')
    appflux = models.FloatField(blank=True, null=True)
    infov = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'calapparent'
        unique_together = (('obs', 'source'),)


class Epoch(models.Model):
    obs = models.OneToOneField('Observation', models.DO_NOTHING, primary_key=True)
    epoch = models.CharField(max_length=9)
    approx_datetime = models.DateTimeField()

    def __str__(self) -> str:
        return self.epoch

    class Meta:
        managed = False
        db_table = 'epoch'


class EpochCompletion(models.Model):
    # This model corresponds to a database view, so it cannot be altered

    epoch = models.CharField(max_length=9, primary_key=True)
    completed = models.IntegerField()
    user = models.TextField()
    pipeline = models.TextField()
    total = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'epoch_completion'


class EpochOverview(models.Model):
    # This model points to a database VIEW
    job_id = models.IntegerField(primary_key=True)
    obs = models.ForeignKey('Observation', models.DO_NOTHING, related_name="epoch_overviews")
    cal_obs = models.ForeignKey('Observation', models.DO_NOTHING, blank=True, null=True, related_name="cal_epoch_overviews")
    epoch = models.CharField(max_length=9)
    user = models.TextField(blank=True, null=True)
    task = models.TextField(blank=True, null=True)
    submission_time = models.DateTimeField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    cal_usable = models.BooleanField(blank=True, null=True)
    cal_notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'epoch_overview'
        ordering = ['obs', 'user', 'task']


class HpcUser(models.Model):
    name = models.CharField(max_length=1023)
    auth_users = models.ManyToManyField(
        User,
        blank=True,
        through='HpcAuthUser',
        through_fields=('hpc_user', 'auth_user'),
        related_name='hpc_users',
    )

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = False
        db_table = 'hpc_user'
        verbose_name = 'HPC User'
        verbose_name_plural = 'HPC Users'


class HpcAuthUser(models.Model):
    hpc_user = models.ForeignKey('HpcUser', models.DO_NOTHING)
    auth_user = models.ForeignKey(User, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'hpc_auth_user'


class Mosaic(models.Model):
    mos_id = models.AutoField(primary_key=True)
    obs = models.ForeignKey('Observation', models.DO_NOTHING, blank=True, null=True)
    job_id = models.IntegerField(blank=True, null=True)
    task_id = models.IntegerField(blank=True, null=True)
    host_cluster = models.CharField(max_length=255, blank=True, null=True)
    user = models.TextField(blank=True, null=True)
    subband = models.TextField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    submission_time = models.IntegerField(blank=True, null=True)
    start_time = models.IntegerField(blank=True, null=True)
    end_time = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'mosaic'


class Observation(models.Model):
    obs = models.IntegerField(primary_key=True, db_column="obs_id")
    projectid = models.TextField(blank=True, null=True)
    lst_deg = models.FloatField(blank=True, null=True)
    starttime = models.TextField(blank=True, null=True)
    duration_sec = models.IntegerField(blank=True, null=True)
    obsname = models.TextField(blank=True, null=True)
    creator = models.TextField(blank=True, null=True)
    azimuth_pointing = models.FloatField(blank=True, null=True)
    elevation_pointing = models.FloatField(blank=True, null=True)
    ra_pointing = models.FloatField(blank=True, null=True)
    dec_pointing = models.FloatField(blank=True, null=True)
    cenchan = models.IntegerField(blank=True, null=True)
    freq_res = models.FloatField(blank=True, null=True)
    int_time = models.FloatField(blank=True, null=True)
    delays = models.TextField(blank=True, null=True)
    calibration = models.BooleanField(blank=True, null=True)
    cal_obs = models.ForeignKey('self', models.DO_NOTHING, blank=True, null=True)
    calibrators = models.TextField(blank=True, null=True)
    peelsrcs = models.TextField(blank=True, null=True)
    flags = models.TextField(blank=True, null=True)
    selfcal = models.IntegerField(blank=True, null=True)
    ion_phs_med = models.IntegerField(blank=True, null=True)
    ion_phs_peak = models.IntegerField(blank=True, null=True)
    ion_phs_std = models.IntegerField(blank=True, null=True)
    archived = models.IntegerField(blank=True, null=True)
    nfiles = models.IntegerField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.obs}"

    #@property
    #def epoch(self):
    #    return f"Epoch{(self.obs - 1335398418)//86400:04d}"

    class Meta:
        managed = False
        db_table = 'observation'
        ordering = ['-obs']


class PipelineStep(models.Model):
    pipeline = models.CharField(max_length=31)
    step_order = models.IntegerField()
    task = models.TextField()

    class Meta:
        managed = False
        db_table = 'pipeline_step'
        unique_together = (('pipeline', 'step_order'),)


class Processing(models.Model):
    job_id = models.IntegerField(primary_key=True)  # The composite primary key (job_id, task_id, host_cluster) found, that is not supported. The first column is selected.
    task_id = models.IntegerField()
    host_cluster = models.CharField(max_length=255)
    submission_time = models.IntegerField(blank=True, null=True)
    task = models.TextField(blank=True, null=True)
    user = models.TextField(blank=True, null=True)
    start_time = models.IntegerField(blank=True, null=True)
    end_time = models.IntegerField(blank=True, null=True)
    obs = models.ForeignKey(Observation, models.DO_NOTHING, blank=True, null=True, related_name='processings')
    cal_obs = models.ForeignKey(Observation, models.DO_NOTHING, blank=True, null=True, related_name='cal_processings')
    status = models.TextField(blank=True, null=True)
    batch_file = models.TextField(blank=True, null=True)
    stderr = models.TextField(blank=True, null=True)
    stdout = models.TextField(blank=True, null=True)
    output_files = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'processing'
        unique_together = (('job_id', 'task_id', 'host_cluster'),)
        ordering = ['-submission_time']
        verbose_name_plural = "Processing"


class Source(models.Model):
    source = models.CharField(primary_key=True, max_length=255)
    raj2000 = models.FloatField(db_column='RAJ2000', blank=True, null=True)  # Field name made lowercase.
    decj2000 = models.FloatField(db_column='DecJ2000', blank=True, null=True)  # Field name made lowercase.
    flux = models.FloatField(blank=True, null=True)
    alpha = models.FloatField(blank=True, null=True)
    beta = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sources'
