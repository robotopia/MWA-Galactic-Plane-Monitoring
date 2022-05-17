#!/usr/bin/env python
from __future__ import print_function

__author__ = ["Paul Hancock", "Natasha Hurley-Walker", "Tim Galvin"]

import os
import sys
import time
import json

import mysql.connector as mysql
import numpy as np
import requests

# Append the service name to this base URL, eg 'con', 'obs', etc.
BASEURL = 'http://ws.mwatelescope.org/metadata'

# This is the list of acceptable observation status' that are 'hard coded' in the
# gleam-x website data/ui models.
OBS_STATUS = ["unprocessed", "downloaded", "calibrated", "imaged", "archived"]

def gpmdb_config():
    host = os.environ["GPMDBHOST"]
    port = os.environ["GPMDBPORT"]
    user = os.environ["GPMDBUSER"]
    passwd = os.environ["GPMDBPASS"]

    return {"host": host, "port": port, "user": user, "password": passwd}


def gpmdb_connect(switch_db=True):

    db_config = gpmdb_config()
    db_con = mysql.connect(**db_config)

    if switch_db:
        db_con.cursor().execute("USE {0}".format('gp_monitor'))
    else:
        print('Warning: You probably do want to switch to the correct database')

    return db_con

# Function to call a JSON web service and return a dictionary: This function by Andrew Williams
# Function to call a JSON web service and return a dictionary: This function by Andrew Williams
def getmeta(service='obs', params=None, level=0):
    
    # Validate the service name
    if service.strip().lower() in ['obs', 'find', 'con']:
        service = service.strip().lower()
    else:
        print("invalid service name: {0}".format(service))
        return
    
    service_url = "{0}/{1}".format(BASEURL, service)
    try:
        response = requests.get(service_url, params=params, timeout=1.)
        response.raise_for_status()

    except requests.HTTPError as error:
        if level <= 2:
            print("HTTP encountered. Retrying...")
            time.sleep(3)
            getmeta(service=service, params=params, level=level+1)
        else:
            raise error
    
    return response.json()


def copy_obs_info(obs_id):

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM observation WHERE obs_id = %s",(obs_id,))
    
    if cur.fetchone()[0] > 0:
        print("\tObsid `{0}` is already imported.".format(obs_id))
        return
    meta = getmeta(service='obs', params={'obs_id':obs_id})
    
    if meta is None:
        print("\t{0} has no metadata!".format(obs_id))
        return

    metadata = meta['metadata']
    
    cur.execute("""
    INSERT INTO observation
    (obs_id, projectid,  lst_deg, starttime, duration_sec, obsname, creator,
    azimuth_pointing, elevation_pointing, ra_pointing, dec_pointing,
    cenchan, freq_res, int_time, delays,
    calibration, cal_obs_id, calibrators,
    peelsrcs, flags, selfcal, ion_phs_med, ion_phs_peak, ion_phs_std,
    nfiles, archived, status
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
    """, (
    obs_id, meta['projectid'], metadata['local_sidereal_time_deg'], meta['starttime'], meta['stoptime']-meta['starttime'], meta['obsname'], meta['creator'],
    metadata['azimuth_pointing'], metadata['elevation_pointing'], metadata['ra_pointing'], metadata['dec_pointing'],
    meta["rfstreams"]["0"]['frequencies'][12], meta['freq_res'], meta['int_time'], json.dumps(meta["rfstreams"]["0"]["xdelays"]),
    metadata['calibration'], None, metadata['calibrators'],
    None, None, None, None, None, None,
    len(meta['files']), False, 'unprocessed'))
    #update_observation(obsid, meta['obsname'], cur)
    
    cur.commit()
    cur.close()

    return


def queue_job(
    job_id,
    task_id,
    host_cluster,
    submission_time,
    obs_id,
    user,
    batch_file,
    stderr,
    stdout,
    task,
):
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """
                INSERT INTO processing
                (job_id, task_id, host_cluster, submission_time, obs_id, user, batch_file, stderr, stdout, task, status)
                VALUES 
                ( %s,%s,%s,%s,%s,%s,%s,%s,%s, %s, 'queued')
                """,
        (
            job_id,
            task_id,
            host_cluster,
            submission_time,
            obs_id,
            user,
            batch_file,
            stderr,
            stdout,
            task,
        ),
    )
    conn.commit()
    conn.close()


def start_job(job_id, task_id, host_cluster, start_time):
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """UPDATE processing 
                   SET status='started', start_time=%s 
                   WHERE job_id =%s AND task_id=%s and host_cluster=%s""",
        (start_time, job_id, task_id, host_cluster),
    )
    conn.commit()
    conn.close()


def finish_job(job_id, task_id, host_cluster, end_time):
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """UPDATE processing 
                   SET status='finished', end_time=%s 
                   WHERE job_id =%s AND task_id=%s and host_cluster=%s""",
        (end_time, job_id, task_id, host_cluster),
    )
    conn.commit()
    conn.close()


def fail_job(job_id, task_id, host_cluster, time):
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """UPDATE processing 
                   SET status='failed', end_time=%s 
                   WHERE job_id =%s AND task_id=%s and host_cluster=%s""",
        (time, job_id, task_id, host_cluster),
    )
    conn.commit()
    conn.close()


def observation_status(obs_id, status):
    """Update the observation table to inform it that obsid has been downloaded

    Args:
        obs_id (int): observation id to update the status of
        status (str): the status to insert for the observation 
    """
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """
                UPDATE observation 
                SET status=%s 
                WHERE obs_id=%s
                """,
        (status.lower(), obs_id,),
    )
    conn.commit()
    conn.close()


def observation_calibrator_id(obs_id, cal_id):
    """A general update function that will modify a spectied key value for a specific observation ID

    Args:
        obs_id (int): observation id to update the status of
        cali_id (int): observation id of the calibrator to insert  
        value (str):  
    """
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """
                UPDATE observation 
                SET cal_obs_id=%s 
                WHERE obs_id=%s
                """,
        (cal_id, obs_id,),
    )
    conn.commit()
    conn.close()


def ion_update(obs_id, ion_path):
    with open(args.ionocsv, "rb") as in_file:
        arr = np.loadtxt(in_file, delimiter=",", skiprows=1)
    
    obsid, med, peak, std = arr
    
    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM observation WHERE obs_id =%s", (obsid,))
    if cur.fetchone()[0] > 0:
        print(
            "Updating observation {0} with median = {1}, peak = {2}, std = {3}".format(
                obsid, med, peak, std
            )
        )
        cur.execute(
            "UPDATE observation SET ion_phs_med = %s, ion_phs_peak = %s, ion_phs_std = %s WHERE obs_id =%s",
            (med, peak, std, obsid),
        )
        cur.commit()
    else:
        print("observation not in database: ", obsid)
    
    cur.close()
    
    return



def require(args, reqlist):
    """
    Determine if the the given requirements are met
    ie that the attributes in the reqlist are not None.
    """
    for r in reqlist:
        if r not in args.__dict__.keys():
            print("Directive {0} requires argument {1}".format(args.directive, r))
            sys.exit(1)

        if getattr(args, r) is None:
            print("Directive {0} requires argument {1}".format(args.directive, r))
            sys.exit(1)

        # an sqlite to mysql change
        if isinstance(args.__dict__[r], str) and "date +%s" in args.__dict__[r]:
            args.__dict__[r] = args.__dict__[r].replace("date +%s", "NOW()")

        if r == "status" and args.status.lower() not in OBS_STATUS:
            print(
                "Observation status `{0}` is not in the allowed list {1}. Exiting without updating. \n".format(
                    args.status, OBS_STATUS
                )
            )
            sys.exit(1)

    return True


if __name__ == "__main__":
    if "GPMTRACK" not in os.environ.keys() or os.environ["GPMRACK"] != "track":
        print("Task process tracking is disabled. ")

        sys.exit(0)


    import argparse

    ps = argparse.ArgumentParser(description="track tasks")
    ps.add_argument("directive", type=str, help="Directive", default=None)
    ps.add_argument("--jobid", type=int, help="Job id from slurm", default=None)
    ps.add_argument("--taskid", type=int, help="Task id from slurm", default=None)
    ps.add_argument("--task", type=str, help="task being run", default=None)
    ps.add_argument("--submission_time", type=int, help="submission time", default=None)
    ps.add_argument("--start_time", type=int, help="job start time", default=None)
    ps.add_argument("--finish_time", type=int, help="job finish time", default=None)
    ps.add_argument("--batch_file", type=str, help="batch file name", default=None)
    ps.add_argument("--obs_id", type=int, help="observation id", default=None)
    ps.add_argument(
        "--cal_id", type=int, help="observation id of calibration data", default=None
    )
    ps.add_argument("--stderr", type=str, help="standard error log", default=None)
    ps.add_argument("--stdout", type=str, help="standard out log", default=None)
    ps.add_argument(
        "--status",
        type=str,
        help="observation status, must belong to {0}".format(OBS_STATUS),
        default=None,
    )
    ps.add_argument(
        "--ion-path", 
        default=None, 
        type=str, 
        help="Path to the csv file produced from the ion-triage procedure."
    )

    args = ps.parse_args()

    args.user = os.environ["GPMUSER"]
    args.host_cluster = os.environ["GPMCLUSTER"]

    if args.directive.lower() == "queue":
        require(
            args,
            [
                "jobid",
                "taskid",
                "host_cluster",
                "submission_time",
                "obs_id",
                "user",
                "batch_file",
                "stderr",
                "stdout",
                "task",
            ],
        )
        queue_job(
            args.jobid,
            args.taskid,
            args.host_cluster,
            args.submission_time,
            args.obs_id,
            args.user,
            args.batch_file,
            args.stderr,
            args.stdout,
            args.task,
        )

    elif args.directive.lower() == "start":
        require(args, ["jobid", "taskid", "host_cluster", "start_time"])
        start_job(args.jobid, args.taskid, args.host_cluster, args.start_time)

    elif args.directive.lower() == "finish":
        require(args, ["jobid", "taskid", "host_cluster", "finish_time"])
        finish_job(args.jobid, args.taskid, args.host_cluster, args.finish_time)

    elif args.directive.lower() == "fail":
        require(args, ["jobid", "taskid", "host_cluster", "finish_time"])
        fail_job(args.jobid, args.taskid, args.host_cluster, args.finish_time)

    elif args.directive.lower() == "obs_status":
        require(args, ["obs_id", "status"])
        observation_status(args.obs_id, args.status)

    elif args.directive.lower() == "obs_calibrator":
        require(args, ["obs_id", "cal_id"])
        observation_calibrator_id(args.obs_id, args.cal_id)

    elif args.directive.lower() == 'ionoupdate':
        require(args, ['obs_id','ion_path'])
        ion_update(args.obs_id, args.ion_path)
    
    elif args.directive.lower() == 'addobs':
        require(args, ['obs_id'])
        copy_obs_info(args.obs_id)

    else:
        print(
            "I don't know what you are asking; please include a queue/start/finish/fail directive"
        )

