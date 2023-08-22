#!/usr/bin/env python

''' make a cube out of a bunch of fits files '''

import sys
from glob import glob
from astropy.io import fits
from astropy.time import Time
import numpy as np

prefix = sys.argv[1]

gpstime = int(prefix[0:10])

files = glob(prefix+"-t????-image.fits")
files = sorted(files)

for ind, f in enumerate(files):
    hdu = fits.open(f)
    if ind == 0:
        cube = hdu[0].data.copy()
#        cube.resize([len(files),hdu[0].data.shape[0],hdu[0].data.shape[1]])
        cube.resize([len(files),hdu[0].data.shape[2],hdu[0].data.shape[3]])
    else:
#        cube[ind,:,:] = hdu[0].data
        cube[ind,:,:] = np.squeeze(hdu[0].data)
    hdu.close()

hdu = fits.open(files[0])

try:
    crval3 = hdu[0].header["FREQ"]
except KeyError:
    crval3 = hdu[0].header["CRVAL3"]

hdu[0].data = cube

# What is timestep
starttime = Time(hdu[0].header["DATE-OBS"], format='isot', scale='utc')
hdu2 = fits.open(files[1])
nexttime = Time(hdu2[0].header["DATE-OBS"], format='isot', scale='utc')
hdu2.close()
delta = nexttime - starttime
delta.format = "sec"
step = int(delta.value)

# Keep record of frequency
hdu[0].header["FREQ"] = crval3

# Replace third axis details
# TODO figure out how to replace CTYPE3 comment (currently says "Central frequency")
hdu[0].header["CTYPE3"] = "TIME"
hdu[0].header["CRPIX3"] = 1.0
hdu[0].header["CRVAL3"] = gpstime
hdu[0].header["CDELT3"] = step
hdu[0].header["CUNIT3"] = "sec"

hdu.writeto("{0}-cube.fits".format(prefix), overwrite=True)

# Do the variance imaging while we're here

std = np.nanstd(hdu[0].data, axis=0)
hdu[0].data = std
hdu.writeto("{0}-stdev.fits".format(prefix), overwrite=True)
