from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from . import models
import json

from astropy.coordinates import SkyCoord, EarthLocation
from astropy.time import Time
import astropy.units as u
import jplephem

import numpy as np

MWA = EarthLocation.of_site('MWA')
MWA_ctr_freq_MHz = 200.32 # WARNING! This info is not in the database, but it should be!
# The DM delay calculation will be wrong for observations not taken at this frequency!!!

def dmdelay(dm, f_MHz):
    return 4.148808e3 * dm / f_MHz**2

# Create your views here.

# The main view: see the state of an epoch's processing at a glance
def EpochOverviewView(request, pipeline, epoch, user):

    # Check that the logged in (Django) user is allowed access to the specified hpc_user
    if not request.user.hpc_users.filter(name=user):
        return HttpResponse('Unauthorized access', status=401)

    observations = models.Observation.objects.all()
    observations = [o for o in observations if o.epoch.epoch == epoch]
    overviews = {o: {eo.task: {"status": eo.status, "cal_obs": eo.cal_obs, "cal_usable": eo.cal_usable, "cal_notes": eo.cal_notes if eo.cal_notes else "", "date": eo.submission_time} for eo in o.epoch_overviews.all() if eo.user == user and eo.epoch == epoch} for o in observations}

    context = {
        'pipeline': pipeline,
        'epoch': epoch,
        'user': user,
        'overviews': overviews,
    }

    try:
        return render(request, f'processing/{pipeline}_epoch_overview.html', context)
    except:
        return HttpResponse(f"Pipeline '{pipeline}' not found", status=404)


def EpochsView(request, pipeline, user):

    # Check that the logged in (Django) user is allowed access to the specified hpc_user
    if not request.user.hpc_users.filter(name=user):
        return HttpResponse('Unauthorized access', status=401)

    epoch_completions = models.EpochCompletion.objects.filter(pipeline=pipeline, user=user)
    partially_complete_epochs = {e.epoch: e.completed/e.total*100 for e in epoch_completions}
    all_epochs = [e['epoch'] for e in models.Epoch.objects.all().order_by('epoch').values('epoch').distinct()]
    completion_data = {e: partially_complete_epochs[e] if e in partially_complete_epochs else 0.0 for e in all_epochs}

    context = {
        'pipeline': pipeline,
        'user': user,
        'completion_data': completion_data,
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


def setEpochCal(request, pipeline, epoch, user):

    # Check that the logged in (Django) user is allowed access to the specified hpc_user
    if not request.user.hpc_users.filter(name=user):
        return HttpResponse('Unauthorized access', status=401)

    # Request method must be 'POST'
    if not request.method == 'POST':
        return HttpResponse(status=400)

    cal_obs_pk = request.POST.get("cal_obs")
    cal_obs = models.Observation.objects.filter(pk=cal_obs_pk, calibration=True).first()

    if cal_obs is None:
        return HttpResponse(f"Calibration observation {cal_obs_pk} not found", status=400)

    observations = models.Observation.objects.filter(epoch__epoch=epoch, calibration=False)
    observations.update(cal_obs=cal_obs)

    for observation in observations:
        observation.save()

    return redirect('epoch_overview', pipeline=pipeline, epoch=epoch, user=user)


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
                }
                for i in criteria_met_idxs
            ]

    return render(request, 'processing/source_finder.html', context)
