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


class Cluster(models.Model):
    name = models.CharField(max_length=31)
    hpc = models.ForeignKey('Hpc', models.DO_NOTHING)
    copy_queue = models.CharField(max_length=31, null=True, blank=True)
    work_queue = models.CharField(max_length=31, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.hpc})"

    class Meta:
        managed = False
        db_table = 'cluster'


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


class Hpc(models.Model):
    name = models.CharField(max_length=127)

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = False
        db_table = 'hpc'
        verbose_name = 'HPC'
        verbose_name_plural = 'HPCs'


class HpcUser(models.Model):
    name = models.CharField(max_length=1023)
    hpc = models.ForeignKey("Hpc", models.DO_NOTHING, related_name="hpc_users")
    auth_users = models.ManyToManyField(
        User,
        blank=True,
        through='HpcAuthUser',
        through_fields=('hpc_user', 'auth_user'),
        related_name='hpc_users',
    )

    def __str__(self) -> str:
        return f"{self.name}@{self.hpc}"

    class Meta:
        managed = False
        db_table = 'hpc_user'
        verbose_name = 'HPC user'
        verbose_name_plural = 'HPC users'


class HpcUserSetting(models.Model):
    hpc_user = models.ForeignKey("HpcUser", models.DO_NOTHING, related_name="hpc_user_settings")
    account = models.CharField(max_length=31, null=True, blank=True)
    max_array_jobs = models.IntegerField(null=True, blank=True)
    basedir = models.CharField(max_length=1023, null=True, blank=True,
                               help_text="The path where the software repository is installed")
    scratchdir = models.CharField(max_length=1023, null=True, blank=True,
                                  help_text="The 'scratch' path where the data are processed")
    logdir = models.CharField(max_length=1023, null=True, blank=True,
                              help_text="The path where to place the log files")
    scriptdir = models.CharField(max_length=1023, null=True, blank=True,
                              help_text="The path where to place the script files")
    container = models.CharField(max_length=1023, null=True, blank=True,
                              help_text="The path where to the singularity container")

    def __str__(self) -> str:
        return f"{self.hpc_user}"

    class Meta:
        managed = False
        db_table = 'hpc_user_setting'
        verbose_name = 'HPC user setting'
        verbose_name_plural = 'HPC user settings'


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
    task_id = models.ForeignKey("Task", models.DO_NOTHING, db_column='task_id', related_name="pipeline_steps")

    def __str__(self) -> str:
        return f"{self.task} ({self.pipeline})"

    class Meta:
        managed = False
        db_table = 'pipeline_step'
        unique_together = (('pipeline', 'step_order'),)
        ordering = ['pipeline', 'step_order']


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


class SlurmHeader(models.Model):
    hpc_user = models.ForeignKey("HpcUser", models.DO_NOTHING, related_name="slurm_headers")
    task = models.ForeignKey("Task", models.DO_NOTHING, related_name="slurm_headers")
    cluster = models.ForeignKey("Cluster", models.DO_NOTHING, related_name="slurm_headers")
    header = models.TextField(primary_key=True)

    def __str__(self) -> str:
        return f"SLURM header ({self.hpc_user} / {self.task} / {self.cluster})"

    class Meta:
        managed = False
        db_table = 'slurm_header'
        ordering = ['hpc_user', 'task', 'cluster']
        verbose_name = 'SLURM header'
        verbose_name_plural = 'SLURM headers'


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



class Task(models.Model):
    name = models.CharField(max_length=31)
    script_name = models.CharField(max_length=31)
    description = models.TextField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.name}"

    class Meta:
        managed = False
        db_table = 'task'
        ordering = ['name']


class TaskClusterSetting(models.Model):
    task = models.ForeignKey("Task", models.DO_NOTHING, related_name="cluster_settings")
    cluster = models.ForeignKey("Cluster", models.DO_NOTHING, related_name="task_settings")
    time_request = models.CharField(max_length=15, null=True, blank=True)
    queue = models.CharField(max_length=31, null=True, blank=True)
    cpus_per_task = models.IntegerField(blank=True, null=True, verbose_name="CPUs per task")
    memory_request_gb = models.IntegerField(blank=True, null=True, verbose_name="Memory request (GB)")
    task_cluster = models.ForeignKey("Cluster", models.DO_NOTHING, null=True, blank=True,
                                     related_name="runnable_task_settings")
    export = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.task} ({self.cluster})"

    class Meta:
        managed = False
        db_table = 'task_cluster_setting'
        unique_together = ['task', 'cluster']
        ordering = ['task', 'cluster']


