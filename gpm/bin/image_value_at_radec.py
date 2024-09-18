#!/usr/bin/env python

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
import argparse

def main(fits_image, coords):
    # Open the FITS file
    hdul = fits.open(fits_image)
    w = WCS(hdul[0].header, naxis=2)

    # Get pixels
    x, y = w.world_to_pixel(coords)
    value = np.squeeze(hdul[0].data[:, :, int(np.round(x)), int(np.round(y))])

    print(fits_image, value)

    hdul.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull out the value of an image at the specified coordinates")
    parser.add_argument("fits_image", help="The path to the FITS image to open")
    parser.add_argument("coords", help="The coordinates in HH:MM:SS.S_DD:MM:SS.S format")
    args = parser.parse_args()

    # Parse the sky coords
    ra, dec = args.coords.split("_")
    coords = SkyCoord(ra, dec, unit=(u.hour, u.deg), frame="fk5")

    # Start main
    main(args.fits_image, coords)
