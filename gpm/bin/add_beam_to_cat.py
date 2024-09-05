#!/usr/bin/env python

from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS
from astropy.coordinates import SkyCoord
import numpy as np
import astropy.units as u
import sys

stem = sys.argv[1]
# Expecting something like 1407161328_deep-MFS-I-image-pb
comp = stem+"_comp_warp-corrected.fits"
beam = stem+"-I-beam.fits"

hc = fits.open(comp)
tab = Table(hc[1].data)

hb = fits.open(beam)
beamdata = hb[0].data
w = WCS(hb[0].header, naxis=2)

singlecoord = SkyCoord(tab["ra"][0], tab["dec"][0], unit=(u.deg, u.deg), frame="fk5")
x, y = w.world_to_pixel(singlecoord)
coordlist = SkyCoord(tab["ra"], tab["dec"], unit=(u.deg, u.deg), frame="fk5")
x, y = w.world_to_pixel(coordlist)
x -= 0.5
y -= 0.5
x, y = x.astype(int), y.astype(int)
tab["beam"] = np.squeeze(beamdata[:,:,y, x])

tab.write(comp.replace(".fits", "_wbeam.fits"), overwrite=True)
