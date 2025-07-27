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
    obs = models.ForeignKey('Observation', models.DO_NOTHING)
    epoch = models.CharField(max_length=9)
    acacia = models.CharField(max_length=127)
    tar_contains_folder = models.BooleanField()
    obstype = models.CharField(max_length=31)

    class Meta:
        managed = False
        db_table = 'backup'
        ordering = ['obs', 'obstype']


class BackupTable(models.Model):
    obs = models.ForeignKey('Observation', models.DO_NOTHING)
    epoch = models.CharField(max_length=9)
    target = models.CharField(max_length=127)
    warp = models.CharField(max_length=127)
    calibration = models.CharField(max_length=127)

    class Meta:
        managed = False
        db_table = 'backup_table'
        ordering = ['obs']


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
    hpc_username = models.TextField()
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
    hpc_user = models.ForeignKey("HpcUser", models.DO_NOTHING, related_name="epoch_overviews")
    task = models.ForeignKey("Task", on_delete=models.DO_NOTHING, related_name="epoch_overviews")
    submission_time = models.DateTimeField(blank=True, null=True)
    status = models.TextField(blank=True, null=True)
    cal_usable = models.BooleanField(blank=True, null=True)
    cal_notes = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'epoch_overview'
        ordering = ['obs', 'hpc_user', 'task']


class DetectionByObs(models.Model):
    # This model points to a database VIEW
    obs_id = models.IntegerField()
    epoch = models.CharField(max_length=9)
    source_name = models.CharField(max_length=255)
    detected = models.CharField(max_length=1)
    duration_sec = models.IntegerField(blank=True, null=True)
    ra_pointing = models.FloatField(blank=True, null=True)
    dec_pointing = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'detections_by_obs'
        ordering = ['obs_id', 'source_name']


class Hpc(models.Model):
    name = models.CharField(max_length=127)

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = False
        db_table = 'hpc'
        verbose_name = 'HPC'
        verbose_name_plural = 'HPCs'


class HpcPath(models.Model):
    path = models.CharField(max_length=511)
    hpc = models.ForeignKey("Hpc", on_delete=models.DO_NOTHING, related_name="paths")

    def __str__(self) -> str:
        return self.path

    class Meta:
        managed = False
        db_table = 'hpc_path'
        verbose_name = 'HPC path'
        verbose_name_plural = 'HPC paths'


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


class Lightcurve(models.Model):
    source = models.ForeignKey('Source', models.DO_NOTHING)
    timestamp = models.DateTimeField(blank=True, null=True)
    obs = models.ForeignKey('Observation', models.DO_NOTHING)
    flux_Jy = models.FloatField()
    flux_Jy_err = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lightcurve'
        constraints = [
            models.UniqueConstraint(fields=['source', 'obs'], name='uniq_src_measurement'),
        ]


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


class Pipeline(models.Model):
    name = models.CharField(max_length=31, unique=True)

    def __str__(self) -> str:
        return f"{self.name}"

    class Meta:
        managed = False
        db_table = 'pipeline'
        ordering = ['name']


class PipelineStep(models.Model):
    pipeline = models.CharField(max_length=31)
    step_order = models.IntegerField()
    task = models.ForeignKey("Task", models.DO_NOTHING, related_name="pipeline_steps")

    def __str__(self) -> str:
        return f"{self.task} ({self.pipeline})"

    class Meta:
        managed = False
        db_table = 'pipeline_step'
        unique_together = (('pipeline', 'step_order'),)
        ordering = ['pipeline', 'step_order']


class Processing(models.Model):
    job_id = models.IntegerField(blank=True, null=True)
    array_task_id = models.IntegerField(blank=True, null=True)
    cluster = models.ForeignKey("Cluster", on_delete=models.DO_NOTHING, related_name="array_jobs")
    submission_time = models.IntegerField(blank=True, null=True)
    task = models.ForeignKey("Task", on_delete=models.DO_NOTHING, related_name="array_jobs")
    hpc_user = models.ForeignKey("HpcUser", on_delete=models.DO_NOTHING, blank=True, null=True, related_name="array_jobs")
    start_time = models.IntegerField(blank=True, null=True)
    end_time = models.IntegerField(blank=True, null=True)
    obs = models.ForeignKey(Observation, models.DO_NOTHING, blank=True, null=True, related_name='array_jobs')
    cal_obs = models.ForeignKey(Observation, models.DO_NOTHING, blank=True, null=True, related_name='cal_array_jobs')
    status = models.TextField(blank=True, null=True)
    batch_file = models.TextField(blank=True, null=True)
    batch_file_path = models.ForeignKey("HpcPath", models.DO_NOTHING, blank=True, null=True, related_name="array_jobs_as_batch_file")
    stderr = models.TextField(blank=True, null=True)
    stderr_path = models.ForeignKey("HpcPath", models.DO_NOTHING, blank=True, null=True, related_name="array_jobs_as_stderr")
    stdout = models.TextField(blank=True, null=True)
    stdout_path = models.ForeignKey("HpcPath", models.DO_NOTHING, blank=True, null=True, related_name="array_jobs_as_stdout")
    output_files = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'processing'
        ordering = ['-submission_time']
        verbose_name_plural = "Processing"


class Source(models.Model):
    name = models.CharField(max_length=255)
    raj2000 = models.FloatField(db_column='raj2000')  # Field name made lowercase.
    decj2000 = models.FloatField(db_column='decj2000')  # Field name made lowercase.
    p0 = models.FloatField(null=True, blank=True, verbose_name="Period (s)")
    pepoch = models.FloatField(null=True, blank=True, verbose_name="PEPOCH (MJD)")
    dm = models.FloatField(null=True, blank=True, verbose_name="DM (pc/cm³)")
    width = models.FloatField(null=True, blank=True, verbose_name="Width (s)")

    def __str__(self) -> str:
        return self.name

    class Meta:
        managed = False
        db_table = 'source'


class Detection(models.Model):
    source = models.ForeignKey("Source", models.DO_NOTHING, related_name="detections")
    obs = models.ForeignKey(Observation, models.DO_NOTHING, blank=True, null=True, related_name='detections')
    detection = models.BooleanField()

    class Meta:
        managed = False
        db_table = 'detection'


class Semester(models.Model):
    name = models.CharField(max_length=31, unique=True)

    def __str__(self) -> str:
        return f"{self.name}"

    class Meta:
        managed = False
        db_table = 'semester'
        ordering = ['name']


class SemesterPlan(models.Model):
    semester = models.ForeignKey("Semester", models.CASCADE, related_name="semester_plans")
    obs = models.ForeignKey("Observation", models.CASCADE, related_name="semester_plans")
    pipeline = models.ForeignKey("Pipeline", models.CASCADE, related_name="semester_plans")

    def __str__(self) -> str:
        return f"{self.semester} - {self.obs}"

    class Meta:
        managed = False
        db_table = 'semester_plan'
        unique_together = ['semester', 'obs']
        ordering = ['semester', 'obs']


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


class UserSessionSetting(models.Model):

    SITE_THEMES = [
        ('l', 'Light'),
        ('d', 'Dark'),
    ]

    user = models.OneToOneField(User, models.CASCADE, related_name="session_settings")
    selected_pipeline = models.CharField(max_length=31, blank=True, null=True)
    selected_semester = models.ForeignKey("Semester", models.SET_NULL, blank=True, null=True, related_name="session_settings")
    selected_hpc_user = models.ForeignKey("HpcUser", models.SET_NULL, blank=True, null=True, related_name="session_settings")
    site_theme = models.CharField(max_length=1, choices=SITE_THEMES, default='l', help_text="Choice of light or dark theme for the website")

    def __str__(self) -> str:
        return f"Session settings for {self.user}"

    class Meta:
        managed = False
        db_table = 'user_session_setting'
        ordering = ['user']
