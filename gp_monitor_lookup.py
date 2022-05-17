from astropy.time import Time
from astropy import units as u

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
            obs_id = obs['mwas.starttime']
            if cal == 1:
                # Select calibrator that matches, default = HerA
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
    parser.add_argument("--startdate", dest='startdate', type=str, default=None,
                        help="start UTC date-time for search (format: 'YYYY-MM-DD HH:MM:SS' ; default = now-24h)")
    parser.add_argument("--stopdate", dest='stopdate', type=str, default=None,
                        help="stop UTC date-time for search (format: 'YYYY-MM-DD HH:MM:SS' ; default = now)")
    parser.add_argument("--project", dest='project', type=str, default='G0080',
                        help="MWA observing project (default = G0080)")
    parser.add_argument("--preferred calibrator", dest='calsrc', type=str, default='HerA',
                        help="Preferred calibrator (default = HerA; options=HerA, J063633-204225, J121834-101851, J153150+240244")
    parser.add_argument("--cal", dest='cal', action="store_true", default=False,
                        help="only look for calibrator observations (will only return most recent)")
    parser.add_argument("--calid", dest='calid', type=int, default=None,
                        help="Look for data surrounding a particular calibrator (overrides other search options)"
    parser.add_argument("--output", dest='output', type=str, default=None,
                        help="Output text file for search args (default = '<project>_<startdate>-<stopdate>_search.txt' (colons will be stripped)")
    parser.add_argument(
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

    if args.calid is None:
        if args.startdate is None:
            start = Time.now() - 24*u.hour
        else:
            start = Time(args.startdate, format="iso", scale="utc")

        if args.stopdate is None:
            stop = start + 24*u.hour
        else:
            stop = Time(args.stopdate,format="iso", scale="utc")
    else:
        gpstime = Time(args.calid, format="gps")
        start = gpstime - 12*u.hour
        stop = gpstime + 12*u.hour

    if args.cal is True:
        cal = 1
    else:
        cal = 0

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
