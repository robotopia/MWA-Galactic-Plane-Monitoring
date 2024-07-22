from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from . import models
import json

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
