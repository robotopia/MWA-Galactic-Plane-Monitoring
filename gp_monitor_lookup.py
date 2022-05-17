#import matplotlib as mpl
#mpl.use("Agg")
#from matplotlib import pyplot as plt
#import matplotlib.ticker as ticker

import numpy as np
#import math

import datetime

from astropy.io import fits
from astropy.time import Time
from astropy import units as u
from astropy.coordinates import SkyCoord

from glob import glob

import urllib.request
import json

import sys

import argparse

BASEURL = "http://ws.mwatelescope.org/"

def getmeta(servicetype='metadata', service='obs', params=None):
    """Given a JSON web servicetype ('observation' or 'metadata'), a service name (eg 'obs', find, or 'con')
       and a set of parameters as a Python dictionary, return a Python dictionary containing the result.
    """
    if params:
        # Turn the dictionary into a string with encoded 'name=value' pairs
        data = urllib.parse.urlencode(params)
    else:
        data = ''

    # Get the data
    try:
        result = json.load(urllib.request.urlopen(BASEURL + servicetype + '/' + service + '?' + data))
    except urllib.error.HTTPError as err:
        print("HTTP error from server: code=%d, response:\n %s" % (err.code, err.read()))
        return
    except urllib.error.URLError as err:
        print("URL or network error: %s" % err.reason)
        return

    # Return the result dictionary
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group1 = parser.add_argument_group("Input/output files")
#    group1.add_argument("--ra", dest='ra', type=float, default=246.99796,
#                        help="RA / longitude value (deg)")
#    group1.add_argument("--dec", dest='dec', type=float, default=-52.58453,
#                        help="Dec / latitude value (deg)")
    group1.add_argument("--startdate", dest='startdate', type=str, default=None,
                        help="start UTC date-time for search (format: 'YYYY-MM-DD HH:MM:SS' ; default = now-24h)")
    group1.add_argument("--stopdate", dest='stopdate', type=str, default=None,
                        help="stop UTC date-time for search (format: 'YYYY-MM-DD HH:MM:SS' ; default = now)")
    group1.add_argument("--project", dest='project', type=str, default='G0080',
                        help="MWA observing project (default = G0080)")
    group1.add_argument("--preferred calibrator", dest='calsrc', type=str, default='HerA',
                        help="Preferred calibrator (default = HerA; options=HerA, J063633-204225, J121834-101851, J153150+240244")
#    group1.add_argument("--minchan", dest='minchan', type=int, default=60,
#                        help="minimum coarse channel number (default = 60)")
#    group1.add_argument("--maxchan", dest='maxchan', type=int, default=180,
#                        help="maximum coarse channel for search (default = 180)")
    group1.add_argument("--cal", dest='cal', action="store_true", default=False,
                        help="only look for calibrator observations (will only return most recent)")
#    group1.add_argument("--separation", dest='separation', type=float, default=50.,
#                        help="Maximum allowable sky separation between pointing centre and source (default = 50deg)")
    group1.add_argument("--output", dest='output', type=str, default=None,
                        help="Output text file for search args (default = '<project>_<date>_search.txt'")
    args = parser.parse_args()

if args.startdate is None:
    duration = datetime.timedelta(hours = 24)
    start = Time(datetime.datetime.now() - duration)
else:
    start = Time(datetime.datetime.strptime(args.startdate,"%Y-%m-%d %H:%M:%S"))

if args.stopdate is None:
    stop = Time(datetime.datetime.now())
else:
    stop = Time(datetime.datetime.strptime(args.stopdate,"%Y-%m-%d %H:%M:%S"))

#t0 = Time(args.pulserefgps, format="gps")
if args.cal is True:
    cal = 1
else:
    cal = 0

print(cal)

try:
    olist = getmeta(service='find', params={'mintime':int(start.gps), 'maxtime':int(stop.gps), 'projectid': args.project, 'calibration':cal, 'dict':1, 'nocache':1})
except:
    print("didn't find anything")
#        # I really don't care about these errors, from looking at the obsids in question they appear to be correlator mode changes and other unuseable observations
    pass
if olist is not None:
    for obs in olist:
        oinfo = getmeta(service='obs', params={'obs_id':obs['mwas.starttime']})
    # Select calibrator
        if args.cal is True:
            if oinfo['metadata']['calibrators'] == args.calsrc:
            # Replace with Andrew's magic look-up service
                print("I would now check whether the data is there and if so, kick off calibration processing")
            # No need to do anything if else -- the calibrator doesn't match the one we want  
        else:
            # Replace with Andrew's magic look-up service
            print("I would now check whether the data is there and if so, kick off onward processing")
else:
    print(f"Failed to find any matching observations within {args.startdate} -- {args.stopdate}")

