from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from . import models
import json

# Create your views here.

# The main view: see the state of an epoch's processing at a glance
def EpochOverviewView(request, epoch, user):

    observations = models.Observation.objects.all()
    observations = [o for o in observations if o.epoch.epoch == epoch]
    overviews = {o: {eo.task: {"status": eo.status, "cal_obs": eo.cal_obs, "cal_usable": eo.cal_usable, "cal_notes": eo.cal_notes if eo.cal_notes else "", "date": eo.submission_time} for eo in o.epoch_overviews.all() if eo.user == user and eo.epoch == epoch} for o in observations}

    context = {
        'epoch': epoch,
        'overviews': overviews,
    }

    return render(request, 'processing/epoch_overview.html', context)


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
