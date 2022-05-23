#!/usr/bin/env python

import urllib.request
import json
import argparse
import logging
from typing import Iterable, Dict, Any, Optional

from astropy.time import Time
from astropy import units as u

import gpm_track as gpmt

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(lineno)d:%(levelname)s %(message)s")
logger.setLevel(logging.INFO)

BASEURL = "http://ws.mwatelescope.org/"

def getmeta(servicetype: str='metadata', service: str='obs', params: Dict[Any, Any]=None) -> Dict[Any, Any]:
    """Given a JSON web servicetype ('observation' or 'metadata'), a service name (eg 'obs', find, or 'con')
       and a set of parameters as a Python dictionary, return a Python dictionary containing the result.

    Args:
        servicetype (str, optional): Desired webservice data return. Defaults to 'metadata'.
        service (str, optional): Desired webservice end point to query. Defaults to 'obs'.
        params (Dict[Any, Any], optional): Additional parameters to pass to webservice. Defaults to None.

    Returns:
        Dict[Any, Any]: Returned data structure from the webservice
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
        raise err
    except urllib.error.URLError as err:
        logging.error("URL or network error: %s" % err.reason)
        raise err

    # Return the result dictionary
    return result

def filter_obs_in_db(rlist: Iterable[int], mode: str='notin'):
    """Stub function to filter obsids based on whether they are in thhe GP monitor database. 
    The default behaviour is only to return obsids if they are NOT in the database, but this
    may be expanded as the use case changes

    Args:
        rlist (Iterable[int]): Collection of obsids to check against the database

    Keyword Args:
        mode (str): The filter mode to apply to the set of provided obsids

    Returns:
        Iterable[int]: Set of obsids not in the database
    
    Raises:
        ValueError: If the provided mode is not known
    """
    filter_modes = ('notin', )

    if mode == 'notin':

        return [obs for obs in rlist if not gpmt.check_imported_obs_id(obs)]
    
    else:
        msg = f"Filter mode not known. Received {mode=}, expected modes in {filter_modes}"
        logger.error(msg)
        raise ValueError(msg)

def do_lookup(
    start: Time, 
    stop: Time, 
    project: str, 
    cal: int, 
    calsrc: int,
    check_in_db: bool=True
) -> Iterable[int]:
    """Obtain a list of obsids to process based on criteria required throughout processing

    Args:
        start (Time): Start time of the observations to search for
        stop (Time): End time of the observations to search for
        project (str): Project code associated with the desired observations
        cal (int): Search only for calibration sources (1 for True, 0 for False, passed to webservice)
        calsrc (int): Obsid of calibration data to search for obsids around
        check_in_db (bool, optional): Confirm that these data have not been processed by the GP monitor database. Defaults to True.

    Returns:
        Iterable[int]: set of obsids to process
    """
    rlist = []
    
    olist = getmeta(
        service='find', 
        params={
            'mintime':int(start.gps), 
            'maxtime':int(stop.gps), 
            'projectid': project, 
            'calibration': cal, 
            'dict': 1, 
            'nocache': 1
        }
    )

    if olist is not None:
        for obs in olist:
            oinfo = getmeta(service='obs', params={'obs_id':obs['mwas.starttime']})
            obs_id = obs['mwas.starttime']
            logger.debug(f"Checking {obs_id=}")

            # Select calibrator that matches, default = HerA
            if cal == 1 and oinfo['metadata']['calibrators'] != calsrc:
                logger.debug(f"Checking calibrator {obs_id=} not {calsrc=}")
                continue
                
            # Confirm that ASVO is ready to hand out the data
            oready = getmeta(service='data_ready', params={'obs_id':obs['mwas.starttime']})
            
            if oready["dataready"] is True:
                logger.debug(f"Data ready {obs_id=} appending")
                rlist.append(obs_id)
        
    # ignore sources not already processed
    if check_in_db:
        logger.debug(f"Checking {rlist=}")
        rlist = filter_obs_in_db(rlist, mode='notin')
    
    logger.debug(f"Returning {rlist=}")
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
                        help="Look for data surrounding a particular calibrator (overrides other search options)")                  
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
