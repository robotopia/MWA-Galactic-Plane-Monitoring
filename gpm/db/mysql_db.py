#!/usr/bin/env python

"""Small set of utility functions to keep the mysql connections in one location. 
"""
import os
import mysql.connector as mysql

__author__ = "Tim Galvin"
dbname = "gpm-processing"

# TODO: Remove this database_configuration business
try:
    import gpm.db.database_configuration as dbc

    dbconfig = dbc.dbconfig
except:
    try:
        host = os.environ["GPMDBHOST"]
        port = os.environ["GPMDBPORT"]
        user = os.environ["GPMDBUSER"]
        passwd = os.environ["GPMDBPASS"]

        dbconfig = {"host": host, "port": port, "user": user, "password": passwd, "database": dbname}

    except:
        dbconfig = None

if dbconfig is None:
    raise ValueError(
        "Database configuration not correctly set. Either place an appropriate configuration into the gpm.db.database_configuration file or export GPMDBHOST, GPMDBPORT, GPMDBUSER and GPMDBPASS environment variables. "
    )

dbconn = "mysql://{0}:{1}@{2}:{3}/{4}".format(
    dbconfig["user"], dbconfig["password"], dbconfig["host"], dbconfig["port"], dbname
)


def connect(switch_db=False):
    """Returns an activate connection to the mysql gpm database
    
    Keyword Paramters:
        switch_db {bool} -- Switch to the gpm database before returning the connection object (Default: {True})
    """
    if dbconfig == None:
        raise ConnectionError(
            "No database connection configuration detected. Ensure an importable `database_configuration` or appropriately set GPMDB* environment variables"
        )

    conn = mysql.connect(**dbconfig)

    if switch_db:
        conn.cursor().execute("USE '{0}'".format(dbname))

    return conn
