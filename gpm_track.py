#!/usr/bin/env python

__author__ = ["Paul Hancock", "Natasha Hurley-Walker", "Tim Galvin"]

import os
import sys
import time
import json
import logging
import argparse
import datetime
from astropy.time import Time
import astropy.units as u

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
    "create_job",
    "create_jobs",
    "queue",
    "queue_jobs",
    "start",
    "finish",
    "fail",
    "obs_status",
    "obs_calibrator",
    "set_epoch_cal",
    "iono_update",
    "import_obs",
    "check_obs",
    "update_apply_cal",
    "obs_flagantennae",
    "get_acacia_path",
    "set_acacia_path",
    "ls_obs_for_cal",
    "obs_epoch",
    "obs_epochs",
    "epoch_obs",
    "obs_processing",
    "epoch_processing",
    "calibrations",
    "last_obs",
    "recent_obs",
    "obs_type",
    "get_logdir",
    "write_slurm_script",
)


def gpmdb_config():
    host = os.environ["GPMDBHOST"]
    port = os.environ["GPMDBPORT"]
    user = os.environ["GPMDBUSER"]
    passwd = os.environ["GPMDBPASS"]
    database = "gpm-processing"

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


def create_job(
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
                (job_id, task_id, host_cluster, submission_time, obs_id, user, batch_file, stderr, stdout, task, status, commit)
                VALUES 
                ( %s,%s,%s,%s,%s,%s,%s,%s,%s, %s, 'queued', %s)
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
            os.environ['GPMGITVERSION'],
        ),
    )
    conn.commit()
    conn.close()


def create_jobs(job_id, host_cluster, obs_ids, user, batch_file, stderr, stdout, task):

    # Cast obs_ids as tuple, just to make sure mysql commands get what they're expecting
    obs_ids = tuple(obs_ids)
    ntasks = len(obs_ids)

    # Replace %A and %a with the appropriate numbers in the stdout and stderr filenames
    stdout = stdout.replace("%A", str(job_id)) # "%A" -> job_id
    stderr = stderr.replace("%A", str(job_id)) # "%A" -> job_id

    stdouts = [stdout.replace("%a", str(i+1)) for i in range(ntasks)] # "%a" -> task_id
    stderrs = [stderr.replace("%a", str(i+1)) for i in range(ntasks)] # "%a" -> task_id

    conn = gpmdb_connect()
    cur = conn.cursor()

    # In the task = 'apply_cal' case, the cal_obs_id field has to be populated with
    # the current value of the cal_obs_id field in the observation table.
    if task == 'apply_cal':
        format_string = ','.join(['%s'] * len(obs_ids)) # = '%s,%s,%s,...'
        cur.execute(f"SELECT cal_obs_id FROM observation WHERE obs_id IN ({format_string})", obs_ids)
        cal_obs_ids = cur.fetchall()
    else:
        cal_obs_ids = tuple([(None,) for i in range(ntasks)])

    #                    v----- task_id starts at 1
    values = [(job_id, i+1, host_cluster, int(obs_ids[i]), user, batch_file,
               stderrs[i], stdouts[i], task, os.environ['GPMGITVERSION'], cal_obs_ids[i][0],)
              for i in range(ntasks)]
            
    '''
    cur.execute(
        """
            SELECT hpc_user_id, logdir_id, scriptdir_id
            FROM hpc_user_setting AS hus
            LEFT JOIN hpc_user AS hu ON hus.hpc_user_id = hu.id
            WHERE hu.name = %s
        """
    '''

    cur.executemany(
        """
                INSERT INTO processing
                (job_id, array_task_id, cluster_id, obs_id, hpc_user_id,
                 batch_file, stderr, stdout,
                 batch_file_path_id, stderr_path_id, stdout_path_id,
                 task_id, commit, cal_obs_id)
                VALUES 
                ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s )
                """,
        values,
    )

    conn.commit()
    conn.close()


def write_slurm_script(task, epoch, host_cluster, user):
    """Uses information from the database to assemble a SLURM script
    """
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute("""SELECT solh.header, t.script_name
        FROM slurm_obs_list_header AS solh
        LEFT JOIN task AS t ON solh.task_id = t.id
        LEFT JOIN cluster AS c ON solh.cluster_id = c.id
        LEFT JOIN hpc_user AS hu ON solh.hpc_user_id = hu.id
        WHERE t.name = %s
          AND solh.epoch = %s COLLATE utf8mb4_bin 
          AND c.name = %s
          AND hu.name = %s
        """,
        (task, epoch, host_cluster, user),
    )
    header, script_name = cur.fetchone()

    # Print shebang
    print("#!/bin/bash -l\n")

    # Print SLURM header
    print(header)

    # Prepare the script
    print("obsnum=$SLURM_ARRAY_TASK_ID")
    print(f"script=$GPMSCRIPT/{task}_${{obsnum}}_${{SLURM_JOB_ID}}.sh")
    print(f"cp $GPMBASE/templates/{script_name}.tmpl $script")
    print(f"srun singularity exec $GPMCONTAINER $script ${{obsnum}}")

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


def queue_job(job_id, task_id, host_cluster, submission_time):
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """UPDATE processing 
                   SET status='queued', submission_time=%s 
                   WHERE job_id =%s AND task_id=%s and host_cluster=%s""",
        (submission_time, job_id, task_id, host_cluster),
    )
    conn.commit()
    conn.close()


def queue_jobs(job_id, host_cluster, submission_time):
    conn = gpmdb_connect()
    cur = conn.cursor()
    cur.execute(
        """UPDATE processing 
                   SET status='queued', submission_time=%s 
                   WHERE job_id =%s AND host_cluster=%s""",
        (submission_time, job_id, host_cluster),
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

def observation_epochs(obs_file):
    """Retrieves the epoch for the observations listed in a given file

    Args:
        obs_file (str): file containing observation ids whose epochs are to be retrieved
    """
    try:
        obs_ids = tuple([int(o) for o in np.loadtxt(obs_file, ndmin=1)])
    except:
        raise ValueError(f"Could not load obsids from file '{obs_file}'")

    format_string = ','.join(['%s'] * len(obs_ids)) # = '%s,%s,%s,...'

    conn = gpmdb_connect()
    cur = conn.cursor()

    # Find out if a row with this obs_id and cal_id already exists
    cur.execute(f"""
            SELECT obs_id, epoch FROM epoch
            WHERE obs_id IN ({format_string})
            """,
            tuple(obs_ids),
            )

    res = cur.fetchall()
    for row in res:
        print(f'{row[0]} {row[1]}')
    conn.close()

def epoch_observations(epoch, exclude_cal=False):
    """Retrieves the observations for a given epoch

    Args:
        epoch (str): epoch name (e.g. "Epoch0032") whose observations are to be retrieved
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    # Get all obs_ids associated with the given epoch
    if exclude_cal == True:
        cur.execute("""
                SELECT e.obs_id FROM epoch AS e
                LEFT JOIN observation AS o ON e.obs_id = o.obs_id
                WHERE e.epoch = %s
                AND o.calibration = false
                """,
                (epoch,),
                )
    else:
        cur.execute("""
                SELECT obs_id FROM epoch
                WHERE epoch = %s
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


def set_epoch_cal(cal_id, epoch):
    """An update function that will set the calibration observation for an entire epoch

    Args:
        cal_id (int): observation id of the calibrator to insert.
        epoch (str): The epoch to apply the calibrator to
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute(
        """
                UPDATE observation
                LEFT JOIN epoch ON observation.obs_id = epoch.obs_id
                SET observation.cal_obs_id = %s 
                WHERE epoch.epoch = %s COLLATE utf8mb4_bin AND observation.calibration = false
                """,
        (cal_id, epoch,),
    )
    conn.commit()
    conn.close()


def get_acacia_path(obs_file, obstype):
    """A select function that will get the acacia path for a specific observation ID

    Args:
        obs_file (str): file containing ObsIDs to get the acacia path for OR
                        a string representing a single ObsID
        obstype: either "target", "calibration", or "warp", representing the
                 stored data product type.
    """

    # Retrieve the obs_ids from the provided obs_file
    try:
        obs_ids = tuple([int(o) for o in np.loadtxt(obs_file, ndmin=1)])
    except:
        logger.info(f"Could not read file: \"{obs_file}\". Will assume it is an obsid.")
        try:
            obs_ids = [int(obs_file)]
        except:
            raise ValueError(f"Could not parse {obs_file} as an obs_id.")

    format_string = ','.join(['%s'] * len(obs_ids)) # = '%s,%s,%s,...'

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute(f"""
                SELECT obs_id, epoch, tar_contains_folder, acacia FROM backup
                WHERE obstype = %s AND obs_id IN ({format_string})
                """,
                tuple([obstype] + obs_ids),
    )
    res = cur.fetchall()
    for row in res:
        print(f'{row[0]} {row[1]} {row[2]} {row[3]}')
    conn.close()


def set_acacia_path(obs_id, obstype, acacia_path):
    """An insert function that will set the acacia path for a specific observation ID and obstype

    Args:
        obs_id (int): ObsIDs to set the acacia path for
        obstype: either "target", "calibration", or "warp", representing the
                 stored data product type.
        acacia_path: a string representing the location of the file on Acacia
    """

    tar_contains_folder = 0 # This is non-zero only for historical uploads. In the current version
                            # of the pipeline, this should always be 0 = False

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute(f"""
                INSERT INTO acacia (obs_id, tar_contains_folder, acacia, obstype)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  tar_contains_folder = %s,
                  acacia = %s
                """,
                (obs_id, tar_contains_folder, acacia_path, obstype, tar_contains_folder, acacia_path,),
    )
    conn.commit()
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
    for row in res:
        try:
            print(f"{datetime.datetime.fromtimestamp(row[0]):19}   {row[1]:15}   {row[2]:9} {row[3]:12}")
        except:
            print(row)
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

def get_last_obs():
    """
    A select function that will get the most recent observation (i.e. the highest obs_id)
    from the database, and prints it to stdout
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("SELECT obs_id FROM observation ORDER BY obs_id DESC LIMIT 1;")
    res = cur.fetchone()
    print(res[0])
    conn.close()

def recent_observations(nhours):
    """
    A select function that will get the most recent observation (i.e. the highest obs_id)
    from the database, and prints it to stdout
    """

    # Get the current time and subtract the number of hours
    nt = Time.now()
    pt = nt - nhours*u.hr

    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("""
                SELECT obs_id FROM observation
                  WHERE obs_id >= %s AND
                        obs_id <= %s AND
                        calibration = FALSE
                  ORDER BY obs_id;
                """,
                (str(pt.gps), str(nt.gps),)
               )
    res = cur.fetchall()
    if len(res) > 0:
        print('\n'.join([str(r[0]) for r in res]))
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


def get_logdir():
    """Gets the GPM log directory from the HPC user environment information from the hpc_user_setting table
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    cur.execute("""
        SELECT logdir
        FROM hpc_user_setting AS hus
        LEFT JOIN hpc_user AS hu ON hus.hpc_user_id = hu.id
        WHERE hu.name = %s
        """,
        (os.environ["USER"],)
    )
    res = cur.fetchone()
    print(res[0])
    conn.close()


def obs_type(obs_id):
    """Prints either 'target' or 'calibration' depending on the type of observation.
    If obs_id doesn't exist, prints nothing.

    Args:
        obs_id (int): observation id whose type is to be printed
    """
    conn = gpmdb_connect()
    cur = conn.cursor()

    # Find out if a row with this obs_id and cal_id already exists
    cur.execute("""
            SELECT calibration FROM observation
            WHERE obs_id = %s
            """,
            (obs_id,),
            )

    res = cur.fetchone()
    if res is not None:
        print('calibration' if res[0] == 1 else 'target')
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
        if r == "obs":
            if (getattr(args, "obs_id") is None and getattr(args, "obs_file") is None):
                logger.error("Directive {0} requires argument either obs_id or obs_file".format(args.directive))
                sys.exit(1)
        else:
                    
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
    ps.add_argument("--host_cluster", type=str, help="the cluster running the task", default=None)
    ps.add_argument("--submission_time", type=int, help="submission time", default=None)
    ps.add_argument("--start_time", type=int, help="job start time", default=None)
    ps.add_argument("--finish_time", type=int, help="job finish time", default=None)
    ps.add_argument("--nhours", type=int, help="Only consider the last NHOURS hours (only applies to directive recent_obs)", default=24)
    ps.add_argument("--batch_file", type=str, help="batch file name", default=None)
    obs_group = ps.add_mutually_exclusive_group()
    obs_group.add_argument("--obs_id", type=int, nargs='*', help="observation id", default=None)
    obs_group.add_argument("--obs_file", type=str, help="File containing Observation IDs", default=None)
    ps.add_argument(
        "--cal_id", type=int, help="observation id of calibration data", default=None
    )
    ps.add_argument("--stderr", type=str, help="standard error log", default=None)
    ps.add_argument("--stdout", type=str, help="standard out log", default=None)
    ps.add_argument("--field", type=str, help="database field to update (update_apply_cal only)", default=None)
    ps.add_argument("--value", type=str, help="database value to insert into \"field\" (update_apply_cal).", default=None)
    ps.add_argument("--epoch", type=str, help="epoch name (e.g. Epoch0123), used for directive epoch_processing", default=None)
    ps.add_argument("--obstype", type=str, help="observation type (for backup purposes). Can be \"target\" (=default), \"calibration\", or \"warp\"", default="target")
    ps.add_argument("--acacia_path", type=str, help="The path to the backup files on Acacia (e.g. \"mwasci:gpm2024/Epoch0123/1234567890.tar.gz\"", default=None)
    ps.add_argument("--exclude_cal", action='store_true', help="For some directives (currently only epoch_obs), do no include calibration observations in the returned list of obsids")
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

    # If only one obs_id was supplied, make sure it is an int
    # (instead of a list containing a single int).
    # This is just a hack so that all the functions which assume
    # obs_id is a single int don't break. Because it's a hack, it has to be
    # UNDONE for any function that relies on it actually being a list.
    # At present, that includes "create_jobs".
    if args.obs_id is not None:
        if len(args.obs_id) == 1:
            setattr(args, "obs_id", args.obs_id[0])

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.directive.lower() == "create_job":
        require(args, ["jobid", "taskid", "host_cluster", "submission_time",
                       "obs_id", "user", "batch_file", "stderr", "stdout", "task"])
        create_job(args.jobid, args.taskid, args.host_cluster, args.submission_time,
                   args.obs_id, args.user, args.batch_file, args.stderr, args.stdout,
                   args.task)

    if args.directive.lower() == "create_jobs":
        require(args, ["jobid", "host_cluster", "obs", "user",
                       "batch_file", "stderr", "stdout", "task"])

        # If obs_file was provided (and obs_id wasn't), pull out the ObsIDs from git file
        if args.obs_file is not None and args.obs_id is None:
            try:
                setattr(args, "obs_id", [int(o) for o in np.loadtxt(args.obs_file, ndmin=1)])
            except:
                logger.info(f"Could not read file: \"{args.obs_file}\". Will assume it is an obsid.")
                try:
                    setattr(args, "obs_id", [int(args.obs_file)])
                except:
                    raise ValueError(f"Could not parse {obs_file} as an obs_id.")

        # Reverse-hack for making sure, in this case, obs_id is a 1D list
        setattr(args, "obs_id", [int(o) for o in np.atleast_1d(args.obs_id)])

        create_jobs(args.jobid, args.host_cluster, args.obs_id, args.user,
                    args.batch_file, args.stderr, args.stdout, args.task)

    elif args.directive.lower() == "start":
        require(args, ["jobid", "taskid", "host_cluster", "start_time"])
        start_job(args.jobid, args.taskid, args.host_cluster, args.start_time)

    elif args.directive.lower() == "finish":
        require(args, ["jobid", "taskid", "host_cluster", "finish_time"])
        finish_job(args.jobid, args.taskid, args.host_cluster, args.finish_time)

    elif args.directive.lower() == "fail":
        require(args, ["jobid", "taskid", "host_cluster", "finish_time"])
        fail_job(args.jobid, args.taskid, args.host_cluster, args.finish_time)

    elif args.directive.lower() == "queue":
        require(args, ["jobid", "taskid", "host_cluster", "submission_time"])
        queue_job(args.jobid, args.taskid, args.host_cluster, args.submission_time)

    elif args.directive.lower() == "queue_jobs":
        require(args, ["jobid", "host_cluster", "submission_time"])
        queue_jobs(args.jobid, args.host_cluster, args.submission_time)

    elif args.directive.lower() == "obs_status":
        require(args, ["obs_id", "status"])
        observation_status(args.obs_id, args.status)

    elif args.directive.lower() == "obs_epoch":
        require(args, ["obs_id"])
        observation_epoch(args.obs_id)

    elif args.directive.lower() == "obs_epochs":
        require(args, ["obs_file"])
        observation_epochs(args.obs_file)

    elif args.directive.lower() == "epoch_obs":
        require(args, ["epoch"])
        epoch_observations(args.epoch, exclude_cal=args.exclude_cal)

    elif args.directive.lower() == "check_obs_status":
        require(args, ["obs_id",])
        status = check_observation_status(args.obs_id)
        
        # putting to stdout to ensure capture by bash
        print(status)

    elif args.directive.lower() == "obs_calibrator":
        require(args, ["obs_id"])
        observation_calibrator_id(args.obs_id, args.cal_id)

    elif args.directive.lower() == "set_epoch_cal":
        require(args, ["cal_id", "epoch"])
        set_epoch_cal(args.cal_id, args.epoch)

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

    elif args.directive.lower() == "get_acacia_path":
        require(args, ["obs_file", "obstype"])
        get_acacia_path(args.obs_file, args.obstype)

    elif args.directive.lower() == "set_acacia_path":
        require(args, ["obs_id", "obstype", "acacia_path"])
        set_acacia_path(args.obs_id, args.obstype, args.acacia_path)

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

    elif args.directive.lower() == "obs_type":
        require(args, ["obs_id"])
        obs_type(args.obs_id)

    elif args.directive.lower() == "last_obs":
        get_last_obs()

    elif args.directive.lower() == "recent_obs":
        require(args, ["nhours"])
        recent_observations(args.nhours)

    elif args.directive.lower() == "get_logdir":
        get_logdir()

    elif args.directive.lower() == "write_slurm_script":
        require(args, ["task", "host_cluster", "epoch", "user"])
        write_slurm_script(args.task, args.epoch, args.host_cluster, args.user)

    else:
        print(
            f"I don't know what you are asking; please include a directive from {DIRECTIVES}"
        )

