#!/usr/bin/env python

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
import argparse

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
    parser.add_argument("coords", help="The coordinates in 'HH:MM:SS.S_DD:MM:SS.S' format")
    parser.add_argument("--error_ctr_coords", help="The coords (in 'HH:MM:SS.S_DD:MM:SS.S' format) for the centre of a region used to calculate the rms error. Default: same as COORDS")
    parser.add_argument("--error_region_size", default=200, type=int, help="The length of one side of a box (in pixels) used for the region used to calculate the rms error. Default: 200")
    args = parser.parse_args()

    # Parse the sky coords
    ra, dec = args.coords.split("_")
    coords = SkyCoord(ra, dec, unit=(u.hour, u.deg), frame="fk5")

    # Parse the sky coords for the error region
    err_ctr_coords_str = args.error_ctr_coords or args.coords
    err_ra, err_dec = err_ctr_coords_str.split("_")
    err_coords = SkyCoord(err_ra, err_dec, unit=(u.hour, u.deg), frame="fk5")

    # Start main
    main(args.fits_image, coords, err_coords=err_coords, err_size=args.error_region_size)
