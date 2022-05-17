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
import logging
import track_task as tt

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(lineno)d:%(levelname)s %(message)s")
logger.setLevel(logging.INFO)

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
        logging.error("HTTP error from server: code=%d, response:\n %s" % (err.code, err.read()))
        return
    except urllib.error.URLError as err:
        logging.error("URL or network error: %s" % err.reason)
        return

    # Return the result dictionary
    return result

# TODO: Stub function for below
# def check_db_to_append(obs_id):
#     in_db = tt.check_imported_obs_id(obs_id)
#     logger.debug(f"{obs_id=} DB {in_db=}")
    
    # return False if in_db else True  

def do_lookup(
    start, 
    stop, 
    project, 
    cal, 
    calsrc,
    check_in_db=True
):
    rlist = []
    try:
        olist = getmeta(service='find', params={'mintime':int(start.gps), 'maxtime':int(stop.gps), 'projectid': project, 'calibration':cal, 'dict':1, 'nocache':1})
    except:
        olist = None
        pass
    
    if olist is not None:
        for obs in olist:
            oinfo = getmeta(service='obs', params={'obs_id':obs['mwas.starttime']})
            # Select calibrator
            obs_id = obs['mwas.starttime']
            if cal == 1:
                if oinfo['metadata']['calibrators'] == calsrc:
                    oready = getmeta(service='data_ready', params={'obs_id':obs['mwas.starttime']})
                    if oready["dataready"] is True:
                        append = True
                        if check_in_db:
                            in_db = tt.check_imported_obs_id(obs_id)
                            logger.debug(f"{obs_id=} DB {in_db=}")
                            
                            append = False if in_db else True  
                        if append:
                            rlist.append(obs['mwas.starttime'])
            
            # else: No need to do anything -- the calibrator doesn't match the one we want  
            else:
                # Replace with Andrew's magic look-up service
                # Maybe this has to be done as a for loop
                oready = getmeta(service='data_ready', params={'obs_id':obs['mwas.starttime']})
                if oready["dataready"] is True:
                    append = True 
                    
                    if check_in_db:
                        in_db = tt.check_imported_obs_id(obs_id)
                        logger.debug(f"{obs_id=} DB {in_db=}")
                        
                        append = False if in_db else True
                    
                    if append:
                        rlist.append(obs_id)
    
    return rlist

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
                        help="Output text file for search args (default = '<project>_<startdate>-<stopdate>_search.txt' (colons will be stripped)")
    group1.add_argument(
        '--skip-db-check', 
        default=False,
        action='store_true',
        help='Will ignore the lookup check to see if data have already been inserted into the GP monitoring database'    
    )
    parser.add_argument(
        '-v',
        '--verbose',
        default=False,
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.startdate is None:
        duration = datetime.timedelta(hours = 24)
        start = datetime.datetime.utcnow() - duration
    else:
        start = datetime.datetime.strptime(args.startdate,"%Y-%m-%d %H:%M:%S")

    if args.stopdate is None:
        stop = datetime.datetime.utcnow()
    else:
        stop = datetime.datetime.strptime(args.stopdate,"%Y-%m-%d %H:%M:%S")

    if args.cal is True:
        cal = 1
    else:
        cal = 0

    # Make into astropy objects so that we can convert to GPS time later
    start, stop = Time(start), Time(stop)
    rlist = do_lookup(
        start, stop, 
        args.project, 
        cal, 
        args.calsrc,
        check_in_db=not args.skip_db_check
    )
    if rlist is False:
        logger.error(f"Failed to find any matching observations within {start} -- {stop} (UTC)")
    else:
        if args.output is not None:
            with open(args.output, "w") as f:
                for obs_id in rlist:
                    f.write(f"{obs_id}\n")
        
        # Bash friendly list
        print(*rlist, sep=" ")


# A potential, if unwieldy, output text file
#        output = "{0}_{1}_{2}_search.txt".format(args.project, start.strftime("%Y%m%dT%H%M%S"), stop.strftime("%Y%m%dT%H%M%S"))
