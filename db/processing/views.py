from django.shortcuts import render
from . import models

# Create your views here.
def EpochOverviewView(request, epoch, user):

    observations = models.Observation.objects.all()
    observations = [o for o in observations if o.epoch == epoch]
    overviews = {o: {eo.task: {"status": eo.status, "cal_obs": eo.cal_obs} for eo in o.epoch_overviews.all() if eo.user == user and eo.epoch == epoch} for o in observations}

    context = {
        'epoch': epoch,
        'overviews': overviews,
    }

    return render(request, 'processing/epoch_overview.html', context)
