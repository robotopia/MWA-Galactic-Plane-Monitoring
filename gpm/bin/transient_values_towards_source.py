#!/usr/bin/env python

import os
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.wcs.utils import skycoord_to_pixel
import astropy.units as u
import argparse
import logging
import mysql.connector as mysql

import matplotlib.pyplot as plt

from transient_search import *

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(lineno)d:%(levelname)s %(message)s")
logger.setLevel(logging.INFO)

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


def sc(data):
    std = np.nanstd(data)
    std = np.nanstd(data[np.abs(data) < 3*std])
    return std

def main(transient_cube_dir, obsid, coord, output_path=None):
    # Open the transient cube
    path = transient_cube_dir + '/{0}_{1}'
    obs = Observation(path, obsid, "transient.hdf5")

    # Get pixels
    x, y = skycoord_to_pixel(coord, obs.wcs)
    values = np.squeeze(obs.data[:, int(np.round(y)), int(np.round(x))])
    timesteps = np.arange(len(values))

    plt.errorbar(timesteps, values, yerr=obs.rms, fmt='o-')
    plt.xlabel("Timestep")
    plt.ylabel("Flux density (Jy)")
    plt.title(f"ObsID: {obsid}, Coord: {coord.ra.to_string(unit=u.hourangle, sep=':')} {coord.dec.to_string(unit=u.deg, sep=':')}")

    if output_path is None:
        output_path = f"{obsid}_{coord.ra.to_string(unit=u.hourangle, sep=':')}_{coord.dec.to_string(unit=u.deg, sep=':')}.png"

    plt.tight_layout()
    plt.savefig(output_path)

    output_txt = output_path[:-4] + ".txt"
    dt = 4 # seconds per timestep. WARNING WARNING HARDCODED VALUE
    t = timesteps*dt + int(obsid)
    np.savetxt(output_txt, np.stack((t, values, np.full(values.shape, obs.rms))).T, fmt="%d %.18e %.18e")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull out the value of an image at the specified coordinates")
    parser.add_argument("transient_cube_dir", help="The (absolute!) directory containing the transient cube to open")
    parser.add_argument("obsid", help="The ObsID (GPS seconds)")
    parser.add_argument("source", help="The source name (which must exist in the database) to use for coordinates")
    #parser.add_argument("--error_ctr_coords", help="The coords (in 'HH:MM:SS.S_DD:MM:SS.S' format) for the centre of a region used to calculate the rms error. Default: same as COORDS")
    args = parser.parse_args()

    # Connect to the database
    conn = gpmdb_connect()
    cur = conn.cursor()

    # Get the source coordinates for the named source from the database
    cur.execute("SELECT raj2000, decj2000 FROM source WHERE name = %s", (args.source,))

    res = cur.fetchone()
    if not res or len(res) == 0:
        raise Exception(f"No source with was found with the name \"{args.source}\"")
    ra, dec = res

    coord = SkyCoord(ra, dec, unit=(u.deg, u.deg), frame="fk5")

    # Start main
    main(args.transient_cube_dir, args.obsid, coord, output_path=f"{args.obsid}_{args.source.replace(' ', '_')}.png")

    # Disconnect from the database
    conn.close()
