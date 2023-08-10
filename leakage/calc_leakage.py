#!/usr/bin/env python

from astropy.io import fits
import numpy as np
from matplotlib import pyplot as plt

# explicit function to normalize array
def normalize_2d(array):
    mx = np.nanmax(array)
    mn = np.nanmin(array)
    array = (array - mn) / (mx - mn)
    return array

img_I = np.squeeze(fits.open(sys.argv[1])[0].data)
img_V = np.squeeze(fits.open(sys.argv[2])[0].data)

cdelt = fits.open(sys.argv[1])[0].header["CDELT2"]

ind = np.indices(img_I.shape)
x, y = ind[0], ind[1]
mid = x[0].shape[0] / 2
dist = cdelt*np.sqrt((x - mid)**2 + (y - mid)**2)

# Not worth looking at anything under ~20-sigma

img_I[img_I < 20*np.nanstd(img_I)] = np.nan
frac = np.abs(img_V / img_I)

fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(dist[~np.isnan(frac)], 1.e2*frac[~np.isnan(frac)], alpha=normalize_2d(img_I[~np.isnan(frac)]))
ax.set_xlabel("Distance from boresight / deg")
ax.set_ylabel("Fractional leakage / %")
#ax.set_xscale("log")
#ax.set_yscale("log")
ax.set_ylim(0.01, 2)
fig.savefig("fractional_leakage.png")
