#!/usr/bin/env python

import os
import sys
import time
import json

import numpy as np
import requests

from astropy.time import Time

# Append the service name to this base URL, eg 'con', 'obs', etc.
BASEURL = "http://ws.mwatelescope.org/metadata"

from django.core.management.base import BaseCommand
from processing.models import Observation

# Function to call a JSON web service and return a dictionary: This function by Andrew Williams
def getmeta(service="obs", params=None, level=0):

    # Validate the service name
    if service.strip().lower() in ["obs", "find", "con"]:
        service = service.strip().lower()
    else:
        print("invalid service name: {0}".format(service))
        return

    service_url = "{0}/{1}".format(BASEURL, service)
    try:
        print(f"Connecting to {service_url=}")
        response = requests.get(service_url, params=params, timeout=5.0)
        response.raise_for_status()

    except requests.HTTPError as error:
        if level <= 2:
            print("HTTP encountered. Retrying...")
            time.sleep(3)
            getmeta(service=service, params=params, level=level + 1)
        else:
            raise error

    return response.json()



class Command(BaseCommand):
    help = "Imports observation metadata from the MWA server into the Observation table"

    def add_arguments(self, parser):
        # Optional argument with flag
        parser.add_argument("--projectid", help="The MWA project ID used to filter observations")
        parser.add_argument("--start_iso", help="Minimum obs date in ISO format (e.g. '2020-01-01')")
        parser.add_argument("--end_iso", help="Maximum obs date in ISO format (e.g. '2020-12-31')")

    def handle(self, *args, **options):
        if 'start_iso' in options.keys():
            mintime = Time(options['start_iso'] + ' 00:00:00', scale='utc', format='iso').gps
        else:
            mintime = ''

        if 'end_iso' in options.keys():
            maxtime = Time(options['end_iso'] + ' 23:59:59', scale='utc', format='iso').gps
        else:
            maxtime = ''

        self.stdout.write(f"Querying MWA database for observations between '{mintime}' and '{maxtime}'")
        if 'projectid' in options.keys():
            self.stdout.write(f"  limited to projectid=\"{options['projectid']}\"")

        # Query the MWA database a page at a time to get complete list of observations
        params = {
            'mintime': mintime,
            'maxtime': maxtime,
            'projectid': projectid,
            'page': 1,
        }
        obs_ids = []
        while True:
            self.stdout.write(f"Page {params['page']}")
            results = getmeta(service="find", params=params)
            if len(results) == 0:
                self.stdout.write("  Empty page. Finished getting everything.")
                break
            obs_ids += [row[0] for row in results] # row[0] is the obs_id as an integer

        # Now go through each observation, get the full metadata, and import into database
        for obs_id in obs_ids:
            meta = getmeta(service="obs", params={"obs_id": obs_id})

            if meta is None:
                self.stderr(f"{obs_id=} has no metadata!")
                continue

            obs = Observation(
                obs=obs_id,
                projectid=meta["projectid"],
                lst_deg=metadata["local_sidereal_time_deg"],
                starttime=meta["starttime"],
                duration_sec=meta["stoptime"] - meta["starttime"],
                obsname=meta["obsname"],
                creator=meta["creator"],
                azimuth_pointing=metadata["azimuth_pointing"],
                elevation_pointing=metadata["elevation_pointing"],
                ra_pointing=metadata["ra_pointing"],
                dec_pointing=metadata["dec_pointing"],
                cenchan=meta["rfstreams"]["0"]["frequencies"][12],
                freq_res=meta["freq_res"],
                int_time=meta["int_time"],
                delays=json.dumps(meta["rfstreams"]["0"]["xdelays"]),
                calibration=metadata["calibration"],
                cal_obs_id=None,
                calibrators=metadata["calibrators"],
                nfiles=len(meta["files"]),
                archived=False,
                status="unprocessed",
            )
            obs.save()

