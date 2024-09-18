#!/usr/bin/env python

import sys
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
import astropy.units as u
import argparse

def main(fits_image, coords):
    # Open the FITS file
    hdul = fits.open(fits_image)
    w = WCS(hdul[0].header, naxis=2)

    # Get pixels
    x, y = w.world_to_pixel(coords)
    value = hdul[0].data[:, :, x, y]

    print(fits_image, value)

    hdul.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull out the value of an image at the specified coordinates")
    parser.add_argument("fits_image", help="The path to the FITS image to open")
    parser.add_argument("ra", type=float, help="The RA in HH:MM:SS.S format")
    parser.add_argument("dec", type=float, help="The declination in DD:MM:SS.S format")
    args = parser.parse_args()

    # Parse the sky coords
    coords = SkyCoord(args.ra, args.dec, unit=(u.hour, u.deg), frame="fk5")

    # Start main
    main(args.fits_image, coords)
