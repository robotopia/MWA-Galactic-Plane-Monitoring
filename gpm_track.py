#!/usr/bin/env python

__author__ = ["Paul Hancock", "Natasha Hurley-Walker", "Tim Galvin"]

import os
import sys
import time
import json
import logging
import argparse
import datetime


import mysql.connector as mysql
import numpy as np
import requests

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(lineno)d:%(levelname)s %(message)s")
logger.setLevel(logging.INFO)

# Append the service name to this base URL, eg 'con', 'obs', etc.
BASEURL = "http://ws.mwatelescope.org/metadata"

# This is the list of acceptable observation status' that are 'hard coded' in the
# gleam-x website data/ui models.
OBS_STATUS = ("unprocessed", "checking" ,"downloaded", "calibrated", "imaged", "archived")
DIRECTIVES = (
    "queue",
    "start",
    "finish",
    "fail",
    "obs_status",
    "obs_calibrator",
    "iono_update",
    "import_obs",
    "check_obs",
    "update_apply_cal",
    "obs_flagantennae",
    "acacia_path",
    "ls_obs_for_cal",
    "obs_epoch",
    "epoch_obs",
    "obs_processing",
    "epoch_processing",
    "calibrations",
)


def gpmdb_config():
    host = os.environ["GPMDBHOST"]
    port = os.environ["GPMDBPORT"]
    user = os.environ["GPMDBUSER"]
    passwd = os.environ["GPMDBPASS"]
    database = "gp_monitor"

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": passwd,
        "database": database,
    }


def gpmdb_connect():
    db_config = gpmdb_config()

    logger.debug(f"Connecting to GP Monitor database - {db_config['host']}:{db_config['port']}")
    db_con = mysql.connect(**db_config)

    return db_con


# Function to call a JSON web service and return a dictionary: This function by Andrew Williams
# Function to call a JSON web service and return a dictionary: This function by Andrew Williams
def getmeta(service="obs", params=None, level=0):

    # Validate the service name
    if service.strip().lower() in ["obs", "find", "con"]:
        service = service.strip().lower()
    else:
        logger.error("invalid service name: {0}".format(service))
        return

    service_url = "{0}/{1}".format(BASEURL, service)
    try:
        logger.debug(f"Connecting to {service_url=}")
        response = requests.get(service_url, params=params, timeout=1.0)
        response.raise_for_status()

    except requests.HTTPError as error:
        if level <= 2:
            logger.debug("HTTP encountered. Retrying...")
            time.sleep(3)
            getmeta(service=service, params=params, level=level + 1)
        else:
            raise error

    return response.json()


def copy_obs_info(obs_id):

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM observation WHERE obs_id = %s", (obs_id,))

    if cur.fetchone()[0] > 0:
        logger.info(f"{obs_id=} is already imported.")
        conn.close()

        return

    meta = getmeta(service="obs", params={"obs_id": obs_id})

    if meta is None:
        logger.error(f"{obs_id=} has no metadata!")
        conn.close()

        return

    metadata = meta["metadata"]
    logger.debug(f"Returned {metadata=}")

    cur.execute(
    """
    INSERT INTO observation
    (obs_id, projectid,  lst_deg, starttime, duration_sec, obsname, creator,
    azimuth_pointing, elevation_pointing, ra_pointing, dec_pointing,
    cenchan, freq_res, int_time, delays,
    calibration, cal_obs_id, calibrators,
    peelsrcs, flags, selfcal, ion_phs_med, ion_phs_peak, ion_phs_std,
    nfiles, archived, status
    )
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
    """,
        (
            obs_id,
            meta["projectid"],
            metadata["local_sidereal_time_deg"],
            meta["starttime"],
            meta["stoptime"] - meta["starttime"],
            meta["obsname"],
            meta["creator"],
            metadata["azimuth_pointing"],
            metadata["elevation_pointing"],
            metadata["ra_pointing"],
            metadata["dec_pointing"],
            meta["rfstreams"]["0"]["frequencies"][12],
            meta["freq_res"],
            meta["int_time"],
            json.dumps(meta["rfstreams"]["0"]["xdelays"]),
            metadata["calibration"],
            None,
            metadata["calibrators"],
            None,
            None,
            None,
            None,
            None,
            None,
            len(meta["files"]),
            False,
            "unprocessed",
        ),
    )

    logger.info(f"Inserted {obs_id=} meta-data")

    conn.commit()
    conn.close()

    return


def check_imported_obs_id(obs_id):

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM observation WHERE obs_id = %s", (obs_id,))

    found = False
    if cur.fetchone()[0] > 0:
        found = True

    conn.close()

    return found


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

def check_observation_status(obs_id):
    """Update the observation table to inform it that obsid has been downloaded

    Args:
        obs_id (int): observation id to update the status of
        status (str): the status to insert for the observation 
    """
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """
                SELECT status 
                FROM observation 
                WHERE obs_id = %s
                """,
        (obs_id,),
    )

    res = cur.fetchall()

    conn.close()

    if len(res) > 1:
        raise ValueError(f"More than a single observation for {obs_id=} found. This should not happen.")
    elif len(res) == 0:
        logger.debug(f"No records returned for {obs_id=}")
        return 'notimported'
    else:
        return res[0][0]
    # Putting to standard out to ensure the output may be captured 
    print(res[0][0])

    conn.close()

    return res[0][0]


def observation_epoch(obs_id):
    """Retrieves the epoch for a given observation

    Args:
        obs_id (int): observation id whose epoch is to be retrieved
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    # Find out if a row with this obs_id and cal_id already exists
    cur.execute("""
            SELECT epoch FROM epoch
            WHERE obs_id = %s
            """,
            (obs_id,),
            )

    res = cur.fetchall()
    if len(res) > 0:
        print(res[0][0])
    conn.close()

def epoch_observations(epoch):
    """Retrieves the observations for a given epoch

    Args:
        epoch (str): epoch name (e.g. "Epoch0032") whose observations are to be retrieved
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    # Find out if a row with this obs_id and cal_id already exists
    cur.execute("""
            SELECT obs_id FROM epoch
            WHERE epoch = %s COLLATE utf8mb4_bin
            """,
            (epoch,),
            )

    res = cur.fetchall()
    print('\n'.join([f"{row[0]}" for row in res]))
    conn.close()

def obs_flagantennae(obs_id):
    """Retrieves a list of antennas to be flagged

    Args:
        obs_id (int): observation id whose antenna flags are to be retrieved
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    # Find out if a row with this obs_id and cal_id already exists
    cur.execute("""
            SELECT antenna FROM antennaflag
            WHERE start_obs_id <= %s AND end_obs_id >= %s
            """,
            (obs_id, obs_id,),
            )

    res = list(dict.fromkeys(cur.fetchall()))
    print(' '.join([str(row[0]) for row in res])) # Print antenna numbers in a space-delimited list
    conn.close()

def update_apply_cal(obs_id, cal_id, field, value):
    """An update function that will signal whether a calibration solution can be transferred to a specific observation ID

    Args:
        obs_id (int): observation id to update the status of
        cal_id (int): observation id of the calibrator to insert  
        field (string): The field to update. Can be "usable" or "notes".
        value (string): The value to be recorded in the database.
    """

    # Using a restricted set of allowed values to prevent against SQL injection
    # (see also https://stackoverflow.com/questions/9394291/python-and-mysqldb-substitution-of-table-resulting-in-syntax-error/9394450#9394450)
    if field not in ["usable", "notes"]:
        raise Exception("The field name must be either 'usable' or 'notes'")

    conn = gpmdb_connect()
    cur = conn.cursor()

    # Find out if a row with this obs_id and cal_id already exists
    cur.execute("""
            SELECT * FROM apply_cal
            WHERE obs_id = %s AND cal_obs_id = %s
            """,
            (obs_id, cal_id,),
            )

    res = cur.fetchall()
    if (len(res) == 0):
        # This obs/calobs combo doesn't exist yet, so add it
        cur.execute("""
                INSERT INTO apply_cal(obs_id, cal_obs_id, """ + field + """)
                VALUES (%s, %s, %s)
                """,
                (obs_id, cal_id, value),
                )
        conn.commit()
    else:
        # This obs/calobs combo already exists, so update it
        cur.execute("""
                    UPDATE apply_cal 
                    SET """ + field + """ = %s 
                    WHERE obs_id = %s AND cal_obs_id = %s
                    """,
                    (value, obs_id, cal_id,),
                    )
        conn.commit()

    # Close the connection
    conn.close()


def observation_calibrator_id(obs_id, cal_id):
    """A select/update function that will get/set the calibration observation for a specific observation ID

    Args:
        obs_id (int): observation id to update the status of
        cal_id (int): observation id of the calibrator to insert. If given, will update. If not given (None), will select.
        value (str):  
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    if cal_id is not None:
        cur.execute(
            """
                    UPDATE observation 
                    SET cal_obs_id=%s 
                    WHERE obs_id=%s
                    """,
            (cal_id, obs_id,),
        )
        conn.commit()
    else:
        cur.execute("""
                SELECT cal_obs_id FROM observation
                WHERE obs_id=%s
                """,
            (obs_id,),
        )
        res = cur.fetchall()
        if len(res) > 0:
            print(res[0][0])
    conn.close()


def acacia_path(obs_id, file_type):
    """A select function that will get the acacia path for a specific observation ID and a given "file type"

    Args:
        obs_id (int): observation id to get the acacia path for
        file_type (str): The type of file as listed in the database
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("""
                SELECT path FROM acacia_file
                WHERE obs_id=%s AND type=%s
                """,
        (obs_id, file_type),
    )
    res = cur.fetchall()
    if len(res) > 0:
        print(res[0][0])
    conn.close()


def ls_obs_for_cal(cal_id):
    """A select function that will get the list of observation to which the given calibration is to be applied.

    Args:
        cal_id (int): calibration observation id
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("""
                SELECT obs_id FROM observation
                WHERE cal_obs_id=%s
                """,
        (cal_id,),
    )
    res = cur.fetchall()
    print('\n'.join([str(row[0]) for row in res]))
    conn.close()


def observation_processing(obs_id):
    """A select function that will get the processing status summary of the given obs id.

    Args:
        obs_id (int): observation id
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    user = os.environ["GPMUSER"]

    cur.execute("""
                SELECT submission_time, task, status, job_id FROM processing
                WHERE obs_id=%s AND user=%s
                ORDER BY submission_time
                """,
        (obs_id, user,),
    )
    res = cur.fetchall()
    print("Submitted             Task              Status         JobID")
    print("----------------------------------------------------------------")
    print('\n'.join([f"{datetime.datetime.fromtimestamp(row[0])}   {row[1]:15}   {row[2]:9} {row[3]:12}" for row in res]))
    conn.close()


def epoch_processing(epoch):
    """A select function that will get the processing status summary of the given epoch.
    In particular, it retrieves the most recent job (excluding status "queued") for each
    obsid in the given epoch.

    Args:
        epoch (str): epoch name (e.g. Epoch0123)
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    user = os.environ["GPMUSER"]

    cur.execute("""
                WITH s1 AS (
                    SELECT e.epoch, p.obs_id, p.submission_time, p.task, p.status, p.job_id,
                        RANK() OVER (PARTITION BY p.obs_id ORDER BY p.submission_time DESC) AS runningorder
                    FROM processing p
                    LEFT JOIN epoch e ON e.obs_id = p.obs_id
                    WHERE p.status != 'queued' AND e.epoch = %s COLLATE utf8mb4_bin AND p.user = %s)
                SELECT epoch, obs_id, submission_time, task, status, job_id
                FROM s1
                WHERE runningorder = 1
                """,
        (epoch, user,),
    )
    res = cur.fetchall()
    print("Epoch       ObsID        Submitted             Task              Status       Job ID")
    print("-------------------------------------------------------------------------------------------")
    print('\n'.join([f"{row[0]}   {row[1]}   {datetime.datetime.fromtimestamp(row[2])}   {row[3]:15}   {row[4]:9} {row[5]:10}" for row in res]))
    conn.close()


def calibrations():
    """A select function that will return the list of all obsids of calibrator observations.
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    user = os.environ["GPMUSER"]

    cur.execute("""
                SELECT obs_id
                FROM observation
                WHERE calibration = 1
                """,
    )
    res = cur.fetchall()
    print('\n'.join([f"{row[0]}" for row in res]))
    conn.close()


def ion_update(obs_id, ion_path):
    with open(ion_path, "rb") as in_file:
        arr = np.loadtxt(in_file, delimiter=",", skiprows=1)

    _, med, peak, std = arr

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM observation WHERE obs_id =%s", (obsid,))
    if cur.fetchone()[0] > 0:
        logger.info(
            "Updating observation {0} with median = {1}, peak = {2}, std = {3}".format(
                obs_id, med, peak, std
            )
        )
        cur.execute(
            "UPDATE observation SET ion_phs_med = %s, ion_phs_peak = %s, ion_phs_std = %s WHERE obs_id =%s",
            (med, peak, std, obs_id),
        )
        cur.commit()
    else:
        logger.error("observation not in database: ", obs_id)

    cur.close()

    return


def require(args, reqlist):
    """
    Determine if the the given requirements are met
    ie that the attributes in the reqlist are not None.
    """
    for r in reqlist:
        if r not in args.__dict__.keys():
            logger.error("Directive {0} requires argument {1}".format(args.directive, r))
            sys.exit(1)

        if getattr(args, r) is None:
            logger.error("Directive {0} requires argument {1}".format(args.directive, r))
            sys.exit(1)

        # an sqlite to mysql change
        if isinstance(args.__dict__[r], str) and "date +%s" in args.__dict__[r]:
            args.__dict__[r] = args.__dict__[r].replace("date +%s", "NOW()")

        if r == "status" and args.status.lower() not in OBS_STATUS:
            logger.error(
                "Observation status `{0}` is not in the allowed list {1}. Exiting without updating. \n".format(
                    args.status, OBS_STATUS
                )
            )
            sys.exit(1)

    return True


if __name__ == "__main__":
    # if "GPMTRACK" not in os.environ.keys() or os.environ["GPMRACK"] != "track":
    #     print("Task process tracking is disabled. ")

    #     sys.exit(0)

    ps = argparse.ArgumentParser(description="track tasks")
    ps.add_argument(
        "directive",
        type=str,
        help=f"Operation to perform. Available directives are: {DIRECTIVES}",
        default=None,
    )
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
    ps.add_argument("--field", type=str, help="database field to update (update_apply_cal only)", default=None)
    ps.add_argument("--value", type=str, help="database value to insert into \"field\" (update_apply_cal and acacia_path).", default=None)
    ps.add_argument("--epoch", type=str, help="epoch name (e.g. Epoch0123), used for directive epoch_processing", default=None)
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
        help="Path to the csv file produced from the ion-triage procedure.",
    )
    ps.add_argument(
        '-v',
        '--verbose',
        default=False,
        action='store_true',
        help='Logs in verbose mode'
    )

    args = ps.parse_args()

    args.user = os.environ["GPMUSER"]
    args.host_cluster = os.environ["GPMCLUSTER"]

    if args.verbose:
        logger.setLevel(logging.DEBUG)

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

    elif args.directive.lower() == "obs_epoch":
        require(args, ["obs_id"])
        observation_epoch(args.obs_id)

    elif args.directive.lower() == "epoch_obs":
        require(args, ["epoch"])
        epoch_observations(args.epoch)

    elif args.directive.lower() == "check_obs_status":
        require(args, ["obs_id",])
        status = check_observation_status(args.obs_id)
        
        # putting to stdout to ensure capture by bash
        print(status)

    elif args.directive.lower() == "obs_calibrator":
        require(args, ["obs_id"])
        observation_calibrator_id(args.obs_id, args.cal_id)

    elif args.directive.lower() == "update_apply_cal":
        require(args, ["obs_id", "cal_id", "field", "value"])
        update_apply_cal(args.obs_id, args.cal_id, args.field, args.value)

    elif args.directive.lower() == "obs_flagantennae":
        require(args, ["obs_id"])
        obs_flagantennae(args.obs_id)

    elif args.directive.lower() == "iono_update":
        require(args, ["obs_id", "ion_path"])
        ion_update(args.obs_id, args.ion_path)

    elif args.directive.lower() == "import_obs":
        require(args, ["obs_id"])
        copy_obs_info(args.obs_id)

    elif args.directive.lower() == "check_obs":
        require(args, ["obs_id"])
        found = check_imported_obs_id(args.obs_id)
        logger.info(f"{args.obs_id=} was {found=}")

    elif args.directive.lower() == "acacia_path":
        require(args, ["obs_id", "value"])
        acacia_path(args.obs_id, args.value)

    elif args.directive.lower() == "ls_obs_for_cal":
        require(args, ["cal_id"])
        ls_obs_for_cal(args.cal_id)

    elif args.directive.lower() == "obs_processing":
        require(args, ["obs_id"])
        observation_processing(args.obs_id)

    elif args.directive.lower() == "epoch_processing":
        require(args, ["epoch"])
        epoch_processing(args.epoch)

    elif args.directive.lower() == "calibrations":
        calibrations()

    else:
        print(
            f"I don't know what you are asking; please include a directive from {DIRECTIVES}"
        )

