from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from . import models
import json
from collections import defaultdict

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

    hpc_user = request.user.session_settings.selected_hpc_user
    semester = request.user.session_settings.selected_semester

    details = models.SemesterPlanProcessingDetail.objects.filter(semester=semester, epoch=epoch, hpc_user=hpc_user)
    details_by_obs = defaultdict(list)

    for detail in details:
        detail.submission_datetime = datetime.fromtimestamp(detail.processing.submission_time)
        details_by_obs[detail.obs].append(detail)
    print(f'{details_by_obs = }')

    context = {
        'epoch': epoch,
        'hpc_user': hpc_user,
        'details_by_obs': dict(details_by_obs),
    }

    return render(request, f'processing/epoch_overview.html', context)


@login_required
def EpochsView(request):

    session_settings = request.user.session_settings
    if not session_settings:
        session_settings = models.UserSessionSetting(user=request.user)
        session_settings.save()

    #while not session_settings.selected_hpc_user or not session_settings.selected_semester:
    #    response = redirect('user_session_settings')
    #    session_settings = request.user.session_settings

    # UP TO HERE: Trying to revamp how this is estimated by using "semesters"
    semester_plan_completions = models.SemesterPlanCompletion.objects.filter(
        semester=session_settings.selected_semester,
    )

    context = {
        'semester_plan_completions': semester_plan_completions,
    }

    return render(request, 'processing/epochs.html', context)


# Change the quality assurance label for a given obs
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
            request.user.session_settings.selected_hpc_user = selected_hpc_user
        except:
            pass
        try:
            selected_semester = models.Semester.objects.get(pk=request.POST.get('selected_semester'))
            request.user.session_settings.selected_semester = selected_semester
        except:
            pass
        request.user.session_settings.site_theme = request.POST.get('site_theme')
        request.user.session_settings.save()

        '''
        if request.POST.get('action') == 'Generate new API token':
            try:
                Token.objects.filter(user=request.user).delete()
            except:
                pass
            Token.objects.create(user=request.user)
        '''

        if request.POST.get('next'):
            return redirect(request.POST.get('next'))

    #token = Token.objects.filter(user=request.user).first()

    context = {
        'semesters': models.Semester.objects.all(),
        'next': request.GET.get('next'),
    }

    return render(request, 'processing/user_settings.html', context)
