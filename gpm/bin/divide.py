#!/usr/bin/env python3

# Divide one fits file by another

import sys

# fits files
try:
    import astropy.io.fits as fits
except ImportError:
    import pyfits as fits

file1=sys.argv[1]
file2=sys.argv[2]
output=sys.argv[3]
try:
    t = float(sys.argv[4])
except:
    t = -999999999999

print("Dividing "+file1+" by "+file2)

hdu1 = fits.open(file1)
hdu2 = fits.open(file2)
hdu1[0].data /= hdu2[0].data
hdu1[0].data[hdu2[0].data<=t] = 0
hdu1.writeto(output,clobber=True)
