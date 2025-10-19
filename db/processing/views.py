from django.shortcuts import render, redirect, resolve_url
from django.http import HttpResponse, JsonResponse
from django.utils.http import urlencode
from django.contrib.auth.decorators import login_required
from processing.hpc_login import hpc_login_required
from django.db.models import Q, F
from django.conf import settings
from . import models
import json
from collections import defaultdict

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, authentication_classes, permission_classes
import rest_framework.exceptions as rest_exceptions
from rest_framework.authtoken.models import Token

from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time
import astropy.units as u
import jplephem

import numpy as np
from datetime import datetime

MWA = EarthLocation.of_site('MWA')
MWA_ctr_freq_MHz = 200.32 # WARNING! This info is not in the database, but it should be!
# The DM delay calculation will be wrong for observations not taken at this frequency!!!

def dmdelay(dm, f_MHz):
    return 4.148808e3 * dm / f_MHz**2

# Create your views here.

# The main view: see the state of an epoch's processing at a glance
@login_required
def EpochOverviewView(request, epoch):

    # Before anything else, check if there are any lingering array jobs which have expired
    # and update their statuses accordingly
    models.ArrayJob.objects.filter(status='started', end_time__lt=int(Time.now().unix)).update(status='expired')

    hpc_user = request.user.session_settings.selected_hpc_user
    semester_plans = request.user.session_settings.selected_semester.semester_plans.filter(obs__epoch__epoch=epoch)
    semester_plan_processing_details = models.SemesterPlanProcessingDetail.objects.filter(
        Q(hpc_user=hpc_user) | Q(hpc_user__isnull=True),
        semester_plan__in=semester_plans,
    ).select_related(
        'semester_plan',
        'semester_plan__obs',
        'semester_plan__obs__epoch',
        'pipeline_step',
        'pipeline_step__pipeline',
        'pipeline_step__task',
    ).order_by('semester_plan__obs__obs', 'pipeline_step')

    details_by_obs = defaultdict(list)
    for semester_plan_processing_detail in semester_plan_processing_details:
        details_by_obs[semester_plan_processing_detail.semester_plan.obs].append(semester_plan_processing_detail)
    details_by_obs = dict(details_by_obs)

    context = {
        'epoch': epoch,
        'hpc_user': hpc_user,
        'details_by_obs': details_by_obs,
    }

    return render(request, f'processing/epoch_overview.html', context)


@login_required
def HPCLogin(request):

    def default_return(error=None):
        context = {
            'next': request.GET.get('next', '/'),
            'error': error,
        }
        return render(request, 'registration/hpc_login.html', context)

    if request.method == 'POST':
        try:
            hpc_user = models.HpcUser.objects.get(pk=int(request.POST.get('hpc_user_id')))
        except:
            return default_return("Invalid HPC account")

        session_settings = request.user.session_settings
        password = request.POST.get('password')
        session_settings.hpc_connect(password)
        if session_settings.hpc_is_connected:
            session_settings.selected_hpc_user = hpc_user
            session_settings.save()
            return redirect(request.GET.get('next'))
        else:
            return default_return("Invalid HPC credentials")

    return default_return()


@login_required
def FindObservation(request):

    epoch = models.Epoch.objects.filter(obs__obs=request.GET.get('obs_id')).first()

    if epoch:
        return redirect('epoch_overview', epoch=epoch.epoch)
    else:
        return redirect('epochs')

@login_required
def EpochsView(request):

    try:
        session_settings = request.user.session_settings
    except:
        session_settings = models.UserSessionSetting(user=request.user)
        session_settings.save()

    semester_plan_completions = models.SemesterPlanCompletion.objects.filter(
        semester=session_settings.selected_semester,
    )

    context = {
        'semester_plan_completions': semester_plan_completions,
    }

    return render(request, 'processing/epochs.html', context)


# This "view" doesn't have a corresponding URL. It is only to be called
# from other views which have already validated the commands.
def RemoteCommand(request, command, hpc_user=None, cluster=None):

    session_settings = request.user.session_settings

    stdout, stderr = session_settings.ssh_command(command, cluster=cluster, hpc_user=hpc_user)

    result = {
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
    }

    return result


@login_required
@hpc_login_required
def LogView(request, processing_id, logfile_type):
    '''
    logfile_type is one of ['batch', 'stdout', 'stderr', 'seff']
    '''

    try:
        processing = models.Processing.objects.get(pk=int(processing_id))
    except:
        return HttpResponse(status=404)

    if processing.hpc_user not in request.user.hpc_users.all():
        return HttpResponse(status=404)

    if logfile_type == 'batch':
        command = f'cat {processing.batch_file_full_path}'
    elif logfile_type == 'stdout':
        command = f'cat {processing.stdout_full_path}'
    elif logfile_type == 'stderr':
        command = f'cat {processing.stderr_full_path}'
    elif logfile_type == 'seff':
        command = f'seff {processing.slurm_id}'
    else:
        return HttpResponse(status=404)

    session_settings = request.user.session_settings
    stdout, stderr = session_settings.hpc_command(command)

    context = {
        'command': command,
        'stdout': stdout,
        'stderr': stderr,
    }

    return render(request, 'processing/log_view.html', context)


@login_required
def ProcessingObsTaskView(request, obs_id, task_id):

    obs = models.Observation.objects.get(obs=obs_id)
    task = models.Task.objects.get(id=task_id)
    if obs is None or task is None:
        return HttpResponse(status=404)

    array_jobs = models.ArrayJob.objects.filter(
        processing__hpc_user=request.user.session_settings.selected_hpc_user,
        obs=obs,
        processing__pipeline_step__task=task,
    ).order_by('-id')

    context = {
        'obs': obs,
        'task': task,
        'array_jobs': array_jobs,
    }

    return render(request, 'processing/processing_obs_task.html', context)



# Change the quality assurance label for a given obs
@login_required
def changeQaStateView(request):

    # Request method must be 'PUT'
    if not request.method == 'PUT':
        return HttpResponse(status=400)

    # Turn the data into a dictionary
    data = json.loads(request.body.decode('utf-8'))

    # Get the relevant obs and cal obs objects
    obs = models.Observation.objects.filter(pk=data['obs']).first()
    cal_obs = models.Observation.objects.filter(pk=data['calObs']).first()

    if obs is None or cal_obs is None:
        return HttpResponse(status=400)

    # How we proceed depends on whether there is an existing row in the
    # 'apply_cal' table for this obs-calobs pair
    apply_cal = models.ApplyCal.objects.filter(obs=obs, cal_obs=cal_obs).first()
    if apply_cal is None:
        apply_cal = models.ApplyCal(obs=obs, cal_obs=cal_obs)

    if data['quality'] == 'good':
        apply_cal.usable = True
    elif data['quality'] == 'bad':
        apply_cal.usable = False
    elif data['quality'] == 'none':
        apply_cal.usable = None

    apply_cal.save()

    return HttpResponse(status=200)


@login_required
def setEpochCal(request, epoch):

    # Request method must be 'POST'
    if not request.method == 'POST':
        return HttpResponse(status=400)

    cal_obs_pk = request.POST.get("cal_obs")

    # Get the observations that will be updated
    observations = models.Observation.objects.filter(epoch__epoch=epoch, calibration=False)

    if cal_obs_pk == 'selfcal':

        for observation in observations:
            observation.cal_obs = observation

    else:
        cal_obs = models.Observation.objects.filter(pk=cal_obs_pk, calibration=True).first()

        if cal_obs is None:
            return HttpResponse(f"Calibration observation {cal_obs_pk} not found", status=400)

        observations.update(cal_obs=cal_obs)

    for observation in observations:
        observation.save()

    return redirect('epoch_overview', epoch=epoch)


@login_required
def sourceFinder(request):

    context = {
        'sources': models.Source.objects.all(),
    }

    if request.method == 'POST':

        selected_source = models.Source.objects.filter(pk=request.POST['selected_source']).first()

        if selected_source is not None:

            context['selected_source'] = selected_source

            # Get the source's coordinates as an astropy SkyCoord object
            selected_source_coord = SkyCoord(selected_source.raj2000, selected_source.decj2000, unit=(u.deg, u.deg), frame='icrs')

            # Go through the available obsids, and convert them to barycentric times

            detections_by_obs = models.DetectionByObs.objects.filter(
                    Q(source_name__isnull=True) | Q(source_name=selected_source.name)) # Should produce unique obs_ids

            obs_start_times = Time([detection_by_obs.obs_id for detection_by_obs in detections_by_obs],
                                   scale='utc', format='gps', location=MWA)
            ltt_bary = obs_start_times.light_travel_time(selected_source_coord, ephemeris='jpl') # Convert to barycentric time
            obs_start_times += ltt_bary

            durations = [duration_by_obs.duration_sec for duration_by_obs in detections_by_obs] * u.s
            epochs = [duration_by_obs.epoch for duration_by_obs in detections_by_obs]
            dm_delay = dmdelay(selected_source.dm or 0, MWA_ctr_freq_MHz) / 86400 # In days
            obs_end_times = obs_start_times + durations

            # Convert the start times to pulse phases
            obs_start_pulses, obs_start_phases = np.divmod((obs_start_times.mjd - selected_source.pepoch - dm_delay)*86400/selected_source.p0, 1)
            obs_end_pulses, obs_end_phases = np.divmod((obs_end_times.mjd - selected_source.pepoch - dm_delay)*86400/selected_source.p0, 1)

            # Criteria to meet:
            # 1) The source is within the specified radius
            maxsep = request.POST.get('maxsep')
            if maxsep is not None and maxsep != '':
                context['maxsep'] = maxsep
                maxsep = float(maxsep) * u.deg
            else:
                maxsep = 360 * u.deg
            ra_pointings = [detection_by_obs.ra_pointing for detection_by_obs in detections_by_obs] * u.deg
            dec_pointings = [detection_by_obs.dec_pointing for detection_by_obs in detections_by_obs] * u.deg
            pointings = SkyCoord(ra_pointings, dec_pointings, frame='icrs')
            separations = selected_source_coord.separation(pointings)
            close_enough = separations < maxsep

            # 2a) The pulse (central) ToA occurs in the observation...
            #     (in which case the pulse number at the start of the observation won't match
            #     the pulse number at the end of the observation, because the way it's set up
            #     with divmod(), the pulse number increments *at* the ToA)
            pulse_in_obs = obs_end_pulses > obs_start_pulses

            # 2b) ...OR we've caught some or all of the first half of the pulse...
            #     (in which case the phase at the end of the observation will be within half
            #     a pulse width of the ToA)
            got_first_half = obs_end_phases > (1.0 - selected_source.width/selected_source.p0/2.0)
            pulse_in_obs = np.logical_or(pulse_in_obs, got_first_half)

            # 2c) ...OR we've caught some or all of the second half of the pulse.
            #     (in which case the phase at the start of the observation will be within half
            #     a pulse width of the ToA)
            got_second_half = obs_start_phases < (selected_source.width/selected_source.p0/2.0)
            pulse_in_obs = np.logical_or(pulse_in_obs, got_second_half)

            # Assemble all the criteria together
            criteria_met = np.logical_and(close_enough, pulse_in_obs)
            criteria_met_idxs = np.where(criteria_met)[0]

            context['matches'] = [
                {
                    'detection_by_obs': detections_by_obs[i.item()],
                    'separation': separations[i.item()].value,
                    'pulse_arrival_s': (1.0 - obs_start_phases[i.item()] - got_second_half[i.item()])*selected_source.p0,
                    'pulse_number': obs_end_pulses[i.item()], # <-- This is not always correct (gives pulse-1 for the case where only the beginning of the pulse is seen) FIXME!!
                }
                for i in criteria_met_idxs
            ]

    return render(request, 'processing/source_finder.html', context)


def backupView(request, epoch):

    backup_rows = models.BackupTable.objects.filter(epoch=epoch)

    context = {
        'backups': backup_rows,
        'epoch': epoch,
    }

    return render(request, 'processing/backups.html', context)


@login_required
def UserSessionSettings(request):

    # Create a UserSetting for this user if needed
    if not hasattr(request.user, 'session_settings'):
        session_settings = models.UserSessionSetting(user=request.user)
        session_settings.save()

    if request.method == 'POST':
        try:
            selected_hpc_user = models.HpcUser.objects.get(pk=request.POST.get('selected_hpc_user'))
            if selected_hpc_user != request.user.session_settings.selected_hpc_user:
                # Selected HPC user has been switched, so disconnect the old one
                request.user.session_settings.hpc_disconnect()
                request.user.session_settings.selected_hpc_user = selected_hpc_user
        except:
            pass
        try:
            selected_semester = models.Semester.objects.get(pk=request.POST.get('selected_semester'))
            request.user.session_settings.selected_semester = selected_semester
        except:
            pass
        try:
            selected_cluster = models.Cluster.objects.get(pk=request.POST.get('selected_cluster'))
            request.user.session_settings.selected_cluster = selected_cluster
        except:
            pass

        request.user.session_settings.site_theme = request.POST.get('site_theme')
        request.user.session_settings.save()

        if request.POST.get('action') == 'Generate new API token':
            try:
                Token.objects.filter(user=request.user).delete()
            except:
                pass
            Token.objects.create(user=request.user)

        if request.POST.get('next'):
            return redirect(request.POST.get('next'))

    token = Token.objects.filter(user=request.user).first()

    # Organise clusters by HPC user
    clusters_by_hpc_user = defaultdict(list)
    hpc_users = request.user.hpc_users.all()
    for hpc_user in hpc_users:
        clusters = models.Cluster.objects.filter(hpc__hpc_users=hpc_user)
        clusters_by_hpc_user[hpc_user.pk] = [{'pk': cluster.pk, 'name': cluster.name} for cluster in clusters]

    context = {
        'semesters': models.Semester.objects.all(),
        'clusters_by_hpc_user': dict(clusters_by_hpc_user),
        'next': request.GET.get('next'),
        'token': token,
    }

    return render(request, 'processing/user_settings.html', context)


@login_required
def HpcUserSettingsView(request, hpc_user_id):

    try:
        hpc_user = models.HpcUser.objects.get(pk=int(hpc_user_id))
    except:
        return HttpResponse(status=404)

    if hpc_user not in request.user.hpc_users.all():
        return HttpResponse(status=404)

    hpc_user_settings = hpc_user.hpc_user_settings
    if hpc_user_settings is None:
        hpc_user_settings = models.HpcUserSettings(hpc_user=hpc_user)
        hpc_user_settings.save()

    if request.method == 'POST':
        hpc_user_settings.account        = request.POST.get('account')
        hpc_user_settings.max_array_jobs = request.POST.get('max_array_jobs')
        hpc_user_settings.basedir        = models.HpcPath.objects.get(pk=request.POST.get('basedir'))
        hpc_user_settings.scratchdir     = models.HpcPath.objects.get(pk=request.POST.get('scratchdir'))
        hpc_user_settings.logdir         = models.HpcPath.objects.get(pk=request.POST.get('logdir'))
        hpc_user_settings.scriptdir      = models.HpcPath.objects.get(pk=request.POST.get('scriptdir'))
        hpc_user_settings.mwalookupdir   = models.HpcPath.objects.get(pk=request.POST.get('mwalookupdir'))
        hpc_user_settings.container      = request.POST.get('container')
        hpc_user_settings.mwapb          = request.POST.get('mwapb')
        hpc_user_settings.sky_model      = request.POST.get('sky_model')
        hpc_user_settings.save()

        if request.GET.get('next') is not None:
            return redirect(request.GET.get('next'))

    hpc_paths = models.HpcPath.objects.filter(owner=hpc_user)

    context = {
        'hpc_user': hpc_user,
        'hpc_paths': hpc_paths,
    }

    return render(request, 'processing/hpc_user_settings.html', context)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def load_profile(request):

    output_text = ""
    status = 200

    # Select hpc_user
    hpc_users = request.user.hpc_users.filter(name=request.GET.get('hpc_user'))
    if not hpc_users.exists():
        try:
            hpc_user = request.user.session_settings.selected_hpc_user
            output_text += f"# HPC user (session default): {hpc_user}\n"
        except:
            output_text += f"# No HPC user selected and no default {request.user}\n"
            status = 400
    elif len(hpc_users) > 1:
        output_text += f"# Multiple HPCs exist for username {request.GET.get('hpc_user')}: {[hu.hpc.name for hu in hpc_users]}. Please specify using query parameter 'hpc'.\n"

    # Get the corresponding HPC settings and print out the corresponding export statements
    output_text = hpc_user.hpc_user_settings.write_exports()

    return HttpResponse(output_text, content_type="text/plain", status=status)


def find_hpc_user(user, hpc_username, hpc_name):

    hpc = models.Hpc.objects.filter(name=hpc_name).first()

    if hpc:
        hpc_users = user.hpc_users.filter(name=hpc_username, hpc=hpc)
    else:
        hpc_users = user.hpc_users.filter(name=hpc_username)

    if not hpc_users.exists():
        try:
            hpc_user = user.session_settings.selected_hpc_user
            return hpc_user
        except:
            raise Exception(f"No HPC user selected and no default for {user}")
    elif len(hpc_users) > 1:
        raise Exception(f"Multiple HPCs exist for username {hpc_username}: {[hu.hpc.name for hu in hpc_users]}")

    return hpc_users.first()


def find_pipeline_step(pipeline_name, task_name):

    if pipeline_name is None:
        raise Exception(f"No pipeline supplied")

    if task_name is None:
        raise Exception(f"No task supplied")

    pipeline = models.Pipeline.objects.filter(name=pipeline_name).first()
    if not pipeline:
        raise Exception(f"Could not find pipeline {pipeline_name}")

    # Select pipeline step
    pipeline_step = pipeline.steps.filter(task__name=task_name).first()
    if not pipeline_step:
        raise Exception(f"Could not find task '{task_name}' in pipeline '{pipeline_name}'")

    return pipeline_step


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def load_job_environment(request):

    output_text = ""

    # Select hpc_user
    try:
        hpc_user = find_hpc_user(request.user, request.GET.get('hpc_user'), request.GET.get('hpc'))
    except Exception as e:
        output_text += f"\nERROR: {e}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    # Write out HPC user settings
    try:
        output_text += hpc_user.hpc_user_settings.write_exports()
    except:
        output_text += f"\nERROR: Cannot find settings for HPC user {hpc_user}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)


    try:
        pipeline_step = find_pipeline_step(
            request.GET.get('pipeline'),
            request.GET.get('task')
        )
    except Exception as e:
        output_text += f"\nERROR: {e}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    pipeline = pipeline_step.pipeline
    task = pipeline_step.task

    output_text += f"export GPMPIPELINE={pipeline.name}\n"
    output_text += f"export GPMTASK={task.name}\n"

    slurm_settings = models.SlurmSettings.objects.filter(pipeline_step=pipeline_step).first()
    if not slurm_settings:
        output_text = f"# Could not find SLURM settings for pipeline step {pipeline_step}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    output_text += slurm_settings.write_exports()

    output_text += f"export GPMOBSSCRIPT={pipeline_step.obs_script}\n"

    return HttpResponse(output_text, content_type="text/plain", status=200)


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_processing_job_status(request):

    output_text = ""

    # Parse all required parameters
    processing_id = request.GET.get('processing_id')
    if processing_id is None:
        output_text += f"\nERROR: processing_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    obs_id = request.GET.get('obs_id')
    if obs_id is None:
        output_text += f"\nERROR: obs_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    status = request.GET.get('status')
    if status is None:
        output_text += f"\nERROR: status is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    # Get the relevant Processing and ArrayJob objects and make sure they exist
    processing = models.Processing.objects.filter(id=processing_id, hpc_user__auth_users=request.user).first()
    if processing is None:
        output_text += f"\nERROR: Could not find processing job with id = {processing_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    array_job = processing.array_jobs.filter(obs__obs=obs_id).first()
    if array_job is None:
        output_text += f"\nERROR: Could not find array job for ObsID = {obs_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    # Update the job's status
    array_job.status = status
    if status == 'started':
        array_job.start_time = int(Time.now().unix)
        slurm_settings = processing.pipeline_step.slurm_settings.first()
        array_job.end_time = slurm_settings.end_time_from_now_as_unix_time
    elif status in ['failed', 'finished']:
        array_job.end_time = int(Time.now().unix)

    try:
        array_job.save()
    except Exception as e:
        output_text += f"\nERROR: {e}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    output_text += f"\nSet status of {processing.pipeline_step.task.name} for Observation {array_job.obs.obs} to '{status}'\n"
    return HttpResponse(output_text, content_type="text/plain", status=200)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_datadir(request):

    # Parse all required parameters
    processing_id = request.GET.get('processing_id')
    if processing_id is None:
        output_text = f"\n# ERROR: processing_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    obs_id = request.GET.get('obs_id')
    if obs_id is None:
        output_text = f"\n# ERROR: obs_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    # Get the relevant Processing and ArrayJob objects and make sure they exist
    processing = models.Processing.objects.filter(pk=processing_id, hpc_user__auth_users=request.user).first()
    if processing is None:
        output_text = f"\n# ERROR: Could not find processing job with id = {processing_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    array_job = processing.array_jobs.filter(obs__obs=obs_id).first()
    if array_job is None:
        output_text = f"\n# ERROR: Could not find array job for ObsID = {obs_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    return HttpResponse(array_job.datadir, content_type="text/plain", status=200)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_calfile(request):

    # Parse all required parameters
    processing_id = request.GET.get('processing_id')
    if processing_id is None:
        output_text = f"\n# ERROR: processing_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    obs_id = request.GET.get('obs_id')
    if obs_id is None:
        output_text = f"\n# ERROR: obs_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    # Get the relevant Processing and ArrayJob objects and make sure they exist
    processing = models.Processing.objects.filter(id=processing_id, hpc_user__auth_users=request.user).first()
    if processing is None:
        output_text = f"\n# ERROR: Could not find processing job with id = {processing_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    array_job = processing.array_jobs.filter(obs__obs=obs_id).first()
    if array_job is None:
        output_text = f"\n# ERROR: Could not find array job for ObsID = {obs_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    return HttpResponse(array_job.calfile, content_type="text/plain", status=200)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_antennaflags(request):

    # Parse all required parameters
    obs_id = request.GET.get('obs_id')
    if obs_id is None:
        output_text = f"\n# ERROR: obs_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    # Get the relevant Processing and ArrayJob objects and make sure they exist
    obs = models.Observation.objects.filter(obs=obs_id).first()
    if obs is None:
        output_text = f"\n# ERROR: Could not find ObsID {obs_id} in database\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    return HttpResponse(obs.antenna_flags_as_str, content_type="text/plain", status=200)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_processing_job(request):
    '''
    Creates new Processing and ArrayJob objects, and responds with text/plain of sbatch script
    Required parameters = obs_ids, pipeline, task, hpc_user, hpc
    Optional parameters = sbatch(=1), debug_mode(=1)
    '''
    # TODO: Make a way to ignore obsids under certin conditions, e.g. status

    if request.GET.get('obs_ids') is None:
        output_text = f"ERROR: obs_ids is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)
    all_obs_ids_and_epochs = set(request.GET.get('obs_ids').split(','))

    # Keep only obs_ids and epochs that are already in the database
    obs_ids_only = {s for s in list(all_obs_ids_and_epochs) if s.isnumeric()}
    epochs_only = all_obs_ids_and_epochs - obs_ids_only
    obss = models.Observation.objects.filter(
        Q(obs__in=list(obs_ids_only)) | Q(epoch__epoch__in=list(epochs_only)),
    ).order_by('obs')
    obs_ids = [str(obs.obs) for obs in obss]

    # Select hpc_user and their settings
    try:
        hpc_user = find_hpc_user(request.user, request.GET.get('hpc_user'), request.GET.get('hpc'))
    except Exception as e:
        output_text = f"ERROR: {e}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    if hpc_user.hpc_user_settings is None:
        output_text = f"ERROR: No settings exist for {hpc_user}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    hpc_user_settings = hpc_user.hpc_user_settings

    # Select the pipeline step
    try:
        pipeline_step = find_pipeline_step(
            request.GET.get('pipeline'),
            request.GET.get('task')
        )
    except Exception as e:
        output_text = f"ERROR: {e}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    pipeline = pipeline_step.pipeline
    task = pipeline_step.task

    slurm_settings = models.SlurmSettings.objects.filter(pipeline_step=pipeline_step).first()
    if not slurm_settings:
        output_text = f"ERROR: Could not find SLURM settings for pipeline step {pipeline_step}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    if len(obs_ids) > 1:
        batch_file = f"{pipeline_step.task.script_name}_{obs_ids[0]}-{obs_ids[-1]}"
        stdout = batch_file + ".o%A_%a"
        stderr = batch_file + ".e%A_%a"
    else:
        batch_file = f"{pipeline_step.task.script_name}_{obs_ids[0]}"
        stdout = batch_file + ".o%A"
        stderr = batch_file + ".e%A"

    processing = models.Processing(
        cluster=slurm_settings.cluster,
        batch_file=batch_file,
        stdout=stdout,
        stderr=stderr,
        batch_file_path=hpc_user_settings.scriptdir,
        stdout_path=hpc_user_settings.logdir,
        stderr_path=hpc_user_settings.logdir,
        hpc_user=hpc_user,
        pipeline_step=pipeline_step,
        commit=settings.GITVERSION,
        debug_mode=(request.GET.get('debug_mode') == '1'),
    )

    try:
        processing.save()
    except Exception as e:
        return HttpResponse(f'ERROR: {e}', content_type="text/plain", status=400)

    end_time = slurm_settings.end_time_from_now_as_unix_time # Just an estimate for now, so that epoch overview page picks up the "latest" job. Will be updated when job actually starts

    for i, obs in enumerate(obss):
        array_job = models.ArrayJob(
            processing=processing,
            array_idx=i+1,
            obs=obs,
            status='queued', # Do this by default, even though it'll be misleading if the job doesn't actually get submitted for some reason
            cal_obs=obs.cal_obs if task.name == 'apply_cal' else None,
            end_time=end_time,
        )
        array_job.save()

    if request.GET.get('sbatch') == '1':
        return HttpResponse(processing.sbatch, content_type="text/plain", status=200)
    else:
        return HttpResponse(f"Processing object created (id={processing.id}) for Observations {', '.join(obs_ids)}", content_type="text/plain", status=200)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_template(request):

    task_name = request.GET.get('task')
    if task_name is None:
        return HttpResponse("ERROR: task is a required parameter\n", content_type="text/plain", status=400)

    task = models.Task.objects.filter(name=task_name).first()
    if task is None:
        return HttpResponse(f"ERROR: task '{task_name}' not found\n", content_type="text/plain", status=400)

    try:
        contents = task.script_contents
    except Exception as e:
        return HttpResponse(f"ERROR: {e}\n", content_type='text/plain', status=400)

    return HttpResponse(contents, content_type='text/plain', status=200)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_job_id(request):

    # Parse all required parameters
    processing_id = request.GET.get('processing_id')
    if processing_id is None:
        output_text = f"\n# ERROR: processing_id is a required parameter\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    processing = models.Processing.objects.filter(id=processing_id, hpc_user__auth_users=request.user).first()
    if processing is None:
        output_text = f"\n# ERROR: Could not find processing job with id = {processing_id}\n"
        return HttpResponse(output_text, content_type="text/plain", status=400)

    job_id = request.GET.get('job_id')
    if job_id is None:
        return HttpResponse("ERROR: job_id is a required parameter\n", content_type="text/plain", status=400)

    try:
        processing.job_id = job_id
        processing.save()
    except Exception as e:
        return HttpResponse(f"ERROR: {e}\n", content_type='text/plain', status=400)

    return HttpResponse("Updated processing id {processing_id} with SLURM JobID {job_id}", content_type='text/plain', status=200)


@login_required
def add_observations_to_semester_plan(request):

    context = {
        'semesters': models.Semester.objects.all(),
        'pipelines': models.Pipeline.objects.all(),
        'calibration_options': ['both', 'calibration', 'target'],
        'epoch': request.GET.get('epoch'),
        'next': request.GET.get('next'),
    }

    try:
        context['semester'] = models.Semester.objects.get(pk=request.GET.get('semester_id'))
    except:
        pass

    if request.method == 'POST':
        epoch = request.POST.get('epoch')
        projectid = request.POST.get('projectid')
        mintime = request.POST.get('mintime')
        maxtime = request.POST.get('maxtime')
        try:
            pipeline = models.Pipeline.objects.get(pk=request.POST.get('pipeline'))
            semester = models.Semester.objects.get(pk=request.POST.get('semester'))
            context['semester'] = semester
        except Exception as e:
            return HttpResponse(f"{e} ({request.POST.get('pipeline')}, {request.POST.get('semester')})", status=400)
        calibration_option = request.POST.get('calibration_option') or 'both'


        obss = models.Observation.objects.all()
        if epoch:
            obss = obss.filter(epoch__epoch=epoch)
        if projectid:
            obss = obss.filter(projectid=projectid)
        if mintime:
            obss = obss.filter(obs__gte=mintime)
        if maxtime:
            obss = obss.filter(obs__lte=maxtime)
        if calibration_option == 'calibration':
            obss = obss.filter(calibration=True)
        elif calibration_option == 'target':
            obss = obss.filter(calibration=False)

        context['added_obs_ids'] = []
        for obs in obss.all():
            semester_plan = models.SemesterPlan(
                obs=obs,
                pipeline=pipeline,
                semester=semester,
            )
            try:
                semester_plan.save()
                context['added_obs_ids'].append(obs.obs)
            except Exception as e:
                context['error'] = f'{e}'

        if request.POST.get('next'):
            return redirect(request.POST.get('next'))

    return render(request, 'processing/add_observations_to_semester_plan.html', context)
