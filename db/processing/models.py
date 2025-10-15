# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
import base64
import os
import paramiko

User = get_user_model()

hpc_clients = {}  # Global state for users "logged into" HPC. Key = HpcUser object, Value = paramikroe.SSHClient object

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
    hostname = models.CharField(max_length=127, null=True, blank=True)

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
    owner = models.ForeignKey("HpcUser", on_delete=models.DO_NOTHING, related_name="hpc_paths")

    def __str__(self) -> str:
        return self.path

    class Meta:
        managed = False
        db_table = 'hpc_path'
        verbose_name = 'HPC path'
        verbose_name_plural = 'HPC paths'
        constraints = [
            models.UniqueConstraint(fields=['path', 'owner'], name='hpc_path_unique'),
        ]
        ordering = ['path']


class HpcUser(models.Model):
    name = models.CharField(max_length=1023, help_text="Username on the HPC")
    hpc = models.ForeignKey("Hpc", models.DO_NOTHING, related_name="hpc_users", verbose_name="HPC")
    auth_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='hpc_users',
        help_text="Which users of this Django app are authorised to change settings for this HPC user.",
        verbose_name="Associated webapp users",
    )

    def __str__(self) -> str:
        return f"{self.name}@{self.hpc}"

    class Meta:
        managed = False
        db_table = 'hpc_user'
        verbose_name = 'HPC user'
        verbose_name_plural = 'HPC users'


class HpcUserSetting(models.Model):
    hpc_user = models.OneToOneField("HpcUser", models.CASCADE, related_name="hpc_user_settings")

    account = models.CharField(max_length=127, null=True, blank=True)

    max_array_jobs = models.IntegerField(null=True, blank=True)

    basedir = models.ForeignKey("HpcPath", on_delete=models.SET_NULL, null=True, blank=True,
                                help_text="The path where the software repository is installed",
                                related_name="hpc_user_settings_as_base")

    scratchdir = models.ForeignKey("HpcPath", on_delete=models.SET_NULL, null=True, blank=True,
                                   help_text="The 'scratch' path where the data are processed",
                                   related_name="hpc_user_settings_as_scratch")

    logdir = models.ForeignKey("HpcPath", on_delete=models.SET_NULL, null=True, blank=True,
                               help_text="The path where to place the log files",
                               related_name="hpc_user_settings_as_log")

    scriptdir = models.ForeignKey("HpcPath", on_delete=models.SET_NULL, null=True, blank=True,
                                  help_text="The path where to place the script files",
                                  related_name="hpc_user_settings_as_script")

    container = models.CharField(max_length=1023, null=True, blank=True,
                                 help_text="The path of the singularity container")

    #start_time_offset_minutes = models.IntegerField(null=True, blank=True, help_text="When a SLURM job is submitted, start the job no sooner from this many minutes from that time.")

    def __str__(self) -> str:
        return f"{self.hpc_user}"

    def write_exports(self):
        output_text = ""
        output_text += f"export GPMBASE={self.basedir.path}\n"
        output_text += f"export GPMSCRATCH={self.scratchdir.path}\n"
        output_text += f"export GPMLOG={self.logdir.path}\n"
        output_text += f"export GPMSCRIPT={self.scriptdir.path}\n"
        output_text += f"export GPMACCOUNT={self.account}\n"
        output_text += f"export GPMMAXARRAYJOBS={self.max_array_jobs}\n"
        output_text += f"export GPMCONTAINER={self.container}\n"
        return output_text

    class Meta:
        managed = False
        db_table = 'hpc_user_setting'
        verbose_name = 'HPC user setting'
        verbose_name_plural = 'HPC user settings'


'''
class HpcAuthUser(models.Model):
    hpc_user = models.ForeignKey('HpcUser', models.DO_NOTHING)
    auth_user = models.ForeignKey(User, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'hpc_auth_user'
'''

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
    pipeline = models.ForeignKey("Pipeline", models.DO_NOTHING, related_name="steps")
    step_order = models.IntegerField()
    task = models.ForeignKey("Task", models.DO_NOTHING, related_name="pipeline_steps")
    cmd_line_options = models.CharField(max_length=127)
    obs_script = models.CharField(max_length=255)

    @property
    def command(self):
        return f'obs_{self.obs_script}.sh {self.cmd_line_options or ""}'

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
    commit = models.CharField(max_length=256)

    @property
    def batch_file_full_path(self):
        return f'{self.batch_file_path.path}/{self.batch_file}'

    @property
    def stdout_full_path(self):
        return f'{self.stdout_path.path}/{self.stdout.replace("%a", str(self.obs.obs)).replace("%A", str(self.job_id))}'

    @property
    def stderr_full_path(self):
        return f'{self.stderr_path.path}/{self.stderr.replace("%a", str(self.obs.obs)).replace("%A", str(self.job_id))}'

    @property
    def slurm_id(self) -> str:
        if self.array_task_id:
            return f'{self.job_id}_{self.array_task_id}'
        return f'{self.job_id}'

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
    selected_hpc_user = models.ForeignKey("HpcUser", models.RESTRICT, blank=True, null=True, related_name="session_settings")
    selected_cluster = models.ForeignKey("Cluster", models.SET_NULL, blank=True, null=True, related_name="session_settings")
    site_theme = models.CharField(max_length=1, choices=SITE_THEMES, default='l', help_text="Choice of light or dark theme for the website")

    @property
    def hpc_is_connected(self):
        hpc_user = self.selected_hpc_user
        return hpc_user in hpc_clients.keys() and (hpc_clients[hpc_user].get_transport() and hpc_clients[hpc_user].get_transport().is_active())

    def hpc_connect(self, password):
        hpc_user = self.selected_hpc_user
        cluster = self.selected_cluster

        if hpc_user not in hpc_clients.keys():
            hpc_clients[hpc_user] = paramiko.SSHClient()
            hpc_clients[hpc_user].set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client = hpc_clients[hpc_user]

        if not self.hpc_is_connected:
            hpc_clients[hpc_user].connect(
                hostname=cluster.hostname,
                username=hpc_user.name,
                password=password,
            )

    def hpc_command(self, command):
        hpc_user = self.selected_hpc_user

        stdin, stdout, stderr = hpc_clients[hpc_user].exec_command(command)

        return stdout.read().decode(), stderr.read().decode()

    def hpc_disconnect(self):
        hpc_user = self.selected_hpc_user

        if hpc_user in hpc_clients.keys():
            hpc_clients[hpc_user].close()
            hpc_clients.pop(hpc_user)

    def __str__(self) -> str:
        return f"Session settings for {self.user}"

    class Meta:
        managed = False
        db_table = 'user_session_setting'
        ordering = ['user']


class SemesterPlanCompletion(models.Model):

    # This model is just a convenient way to access an SQL VIEW

    semester = models.ForeignKey("Semester", models.DO_NOTHING)
    epoch = models.CharField(max_length=9)
    nfinished = models.IntegerField()
    ntotal = models.IntegerField()
    fraction_finished = models.FloatField()

    @property
    def percent_finished(self):
        return self.fraction_finished*100

    class Meta:
        managed = False
        db_table = 'semester_plan_completion'
        ordering = ['semester', 'epoch']


class SemesterPlanProcessingDetail(models.Model):

    # This model is just a convenient way to access an SQL VIEW

    semester = models.ForeignKey("Semester", models.DO_NOTHING)
    epoch = models.CharField(max_length=9)
    obs = models.ForeignKey("Observation", models.DO_NOTHING)
    processing = models.ForeignKey("Processing", models.DO_NOTHING)
    hpc_user = models.ForeignKey("HpcUser", models.DO_NOTHING)
    task = models.ForeignKey("Task", models.DO_NOTHING)
    pipeline_step = models.ForeignKey("PipelineStep", models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'semester_plan_processing_detail'
        ordering = ['semester', 'obs', 'pipeline_step']


class SlurmSettings(models.Model):

    pipeline_step = models.ForeignKey("PipelineStep", on_delete=models.CASCADE, related_name="slurm_settings")
    cluster = models.ForeignKey("Cluster", on_delete=models.CASCADE, related_name="slurm_settings")
    begin = models.CharField(max_length=127, null=True, blank=True)
    mem   = models.CharField(max_length=15, null=True, blank=True)
    time  = models.CharField(max_length=31, null=True, blank=True)
    ntasks_per_node = models.CharField(max_length=31, null=True, blank=True)
    partition = models.CharField(
        max_length=1,
        choices=[
            ('w', 'Work'),
            ('c', 'Copy'),
        ],
        null=True, blank=True
    )
    account = models.CharField(max_length=127, null=True, blank=True)

    @property
    def partition_name(self):
        if self.partition == 'c':
            return self.cluster.copy_queue
        if self.partition == 'w':
            return self.cluster.work_queue
        return None

    def write_slurm_header(self):
        header = ""
        header += f"#SBATCH --clusters={self.cluster.name}\n" if self.cluster else ""
        header += f"#SBATCH --begin={self.begin}\n" if self.begin else ""
        header += f"#SBATCH --mem={self.mem}\n" if self.mem else ""
        header += f"#SBATCH --time={self.time}\n" if self.time else ""
        header += f"#SBATCH --ntasks-per-node={self.ntasks_per_node}\n" if self.ntasks_per_node else ""
        header += f"#SBATCH --partition={self.partition_name}\n" if self.partition_name else ""
        header += f"#SBATCH --account={self.account}\n" if self.account else ""
        return header

    def write_exports(self):
        exports = ""
        exports += f"export GPMCLUSTER={self.cluster.name}\n" if self.cluster else ""
        exports += f"export GPMBEGIN={self.begin}\n" if self.begin else ""
        exports += f"export GPMABSMEMORY={self.mem}\n" if self.mem else ""
        exports += f"export GPMTIME={self.time}\n" if self.time else ""
        exports += f"export GPMNTASKSPERNODE={self.ntasks_per_node}\n" if self.ntasks_per_node else ""
        exports += f"export GPMSTANDARDQ={self.partition_name}\n" if self.partition_name else ""
        exports += f"export GPMCOPYQ={self.partition_name}\n" if self.partition_name else ""
        exports += f"export GPMACCOUNT={self.account}\n" if self.account else ""

        return exports

    class Meta:
        managed = False
        db_table = 'slurm_settings'
        ordering = ['cluster', 'pipeline_step']
        constraints = [
            models.UniqueConstraint(fields=['cluster', 'pipeline_step'], name='slurm_settings_unique'),
        ]
        verbose_name = 'SLURM settings'
