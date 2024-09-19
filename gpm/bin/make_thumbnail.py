#!/usr/bin/env python

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import astropy.units as u
import argparse
import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.use("Agg")  # So does not use display

def main(fits_image, coords, size, outplot):
    # Open the FITS file
    hdul = fits.open(fits_image)
    w = WCS(hdul[0].header, naxis=2)

    # Get pixels
    x, y = w.world_to_pixel(coords)
    #try:
    # Only bother writing out if the value at the target pixel is not nan
    value = hdul[0].data[:, :, int(y), int(x)]
    if np.isnan(value):
        raise Exception("Centre of thumbnail is nan")

    # Get thumbnail
    x0, x1 = int(x - size/2), int(x + size/2)
    y0, y1 = int(y - size/2), int(y + size/2)
    wx0, wy0 = w.wcs_pix2world(x0, y0, 1)
    wx1, wy1 = w.wcs_pix2world(x1, y1, 1)
    extent = (wx0/15 + 24, wx1/15 + 24, wy0, wy1)
    aspect = 1/(np.cos(coords.dec)*15)
        
    thumbnail = np.squeeze(hdul[0].data[:, :, y0:y1, x0:x1])

    fig = plt.figure(figsize=(4,3.5))
    fig.add_subplot(111)
    plt.imshow(thumbnail, origin='lower', aspect=aspect, cmap=plt.cm.viridis, extent=extent)
    plt.xlabel('RA (hours)')
    plt.ylabel('Dec (deg)')

    plt.tight_layout()
    plt.savefig(outplot)

    #print(hdul[0].header['DATE-OBS'], value, rms)
    #except:
    #    # This pixel is probably not in this image. Ignore it!
    #    pass

    hdul.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pull out the value of an image at the specified coordinates")
    parser.add_argument("fits_image", help="The path to the FITS image to open")
    parser.add_argument("coords", help="The coordinates in 'HH:MM:SS.S_DD:MM:SS.S' format")
    parser.add_argument("--size", default=200, type=int, help="The number of pixels along one side of the (square) thumbnail. Default: 200")
    parser.add_argument("--outplot", help="The output plot filename. Default: same as fits_image, but with \".fits\" replaced with \"_[COORDS].png\"")
    args = parser.parse_args()

    # Parse the sky coords
    ra, dec = args.coords.split("_")
    coords = SkyCoord(ra, dec, unit=(u.hour, u.deg), frame="fk5")

    # Set output filename
    outplot = args.outplot or args.fits_image.replace(".fits", f"_{ra}_{dec}.png")

    # Start main
    main(args.fits_image, coords, args.size, outplot)
