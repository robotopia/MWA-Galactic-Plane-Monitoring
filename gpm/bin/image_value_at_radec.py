#!/usr/bin/env python

import os
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
import argparse
import logging
import mysql.connector as mysql

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
    std = np.std(data)
    std = np.std(data[np.abs(data) < 3*std])
    return std


def main(fits_image, coords, err_coords=None, err_size=None):
    # Open the FITS file
    hdul = fits.open(fits_image)
    w = WCS(hdul[0].header, naxis=2)

    # Get pixels
    x, y = w.world_to_pixel(coords)
    try:
        value = np.squeeze(hdul[0].data[:, :, int(np.round(y)), int(np.round(x))])

        # Only bother writing out non-nan values
        if not np.isnan(value):
            if err_coords is not None and err_size is not None:
                # Get error
                err_x, err_y = w.world_to_pixel(err_coords)
                rad = err_size//2
                rms = sc(hdul[0].data[:, :, int(err_y)-rad:int(err_y)+rad, int(err_x)-rad:int(err_x)+rad])

                print(hdul[0].header['DATE-OBS'], value, rms)

            else:

                print(hdul[0].header['DATE-OBS'], value)
    except:
        # This pixel is probably not in this image. Ignore it!
        pass

    hdul.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull out the value of an image at the specified coordinates")
    parser.add_argument("fits_image", help="The path to the FITS image to open")
    parser.add_argument("source", help="The source name (which must exist in the database) to use for coordinates")
    #parser.add_argument("--error_ctr_coords", help="The coords (in 'HH:MM:SS.S_DD:MM:SS.S' format) for the centre of a region used to calculate the rms error. Default: same as COORDS")
    parser.add_argument("--error_region_size", default=200, type=int, help="The length of one side of a box (in pixels) used for the region used to calculate the rms error. Default: 200")
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

    coords = SkyCoord(ra, dec, unit=(u.deg, u.deg), frame="fk5")

    # Start main
    main(args.fits_image, coords, err_coords=coords, err_size=args.error_region_size)

    # Disconnect from the database
    conn.close()
