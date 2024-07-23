#!/usr/bin/env python

from astropy.io import fits
import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import argparse
import matplotlib as mpl
import sys
from scipy.optimize import curve_fit

# explicit function to normalize array
def normalize_2d(array):
    mx = np.nanmax(array)
    mn = np.nanmin(array)
    array = (array - mn) / (mx - mn)
    return array

def scstd(data):
    std = np.nanstd(data)
    std = np.nanstd(data[np.abs(data) < 3*std])
    return std

# https://www.geeksforgeeks.org/3d-curve-fitting-with-python/
def func(xy, a, b, c, d, e, f):
    x, y = xy
    return a + b*x + c*y + d*x**2 + e*y**2 + f*x*y

def do_fit(Inonpb, Ipb, Vpb, nsigma=20, makePlots=False, subchan=None):

    img_I_npb = np.squeeze(fits.open(Inonpb)[0].data)
    img_I = np.squeeze(fits.open(Ipb)[0].data)
    img_V = np.squeeze(fits.open(Vpb)[0].data)

    cdelt = fits.open(Inonpb)[0].header["CDELT2"]
    xmax, ymax = img_I.shape[0], img_I.shape[1]
    ind = np.indices(img_I.shape)
    x, y = ind[0], ind[1]

    # Make a box of the inside 1/3rd of the image where hopefully we're artefact-free
    imsize = img_I.shape[0]
    l = int(np.round(imsize/3))
    r = imsize - l

    # Not worth looking at anything under some brightness (use sigma-clipping to find rms)
    img_I[img_I_npb < nsigma*scstd(img_I_npb[l:r,l:r])] = np.nan
    frac = img_V / img_I

    x = x[~np.isnan(frac)]
    y = y[~np.isnan(frac)]
    z = 1.e2*np.ndarray.flatten(frac[~np.isnan(frac)])

# Perform curve fitting
    popt, pcov = curve_fit(func, (y, x), z)

    if makePlots is True:
        obsid = Inonpb[0:10]
        minleakage = np.nanmin(z)
        maxleakage = np.nanmax(z)

        fig = plt.figure()
        ax = fig.add_subplot(111)
    # Reversing these to match that the RA and Dec axes are reversed in the FITS image
        sc = ax.scatter(y, x, c=z, vmin=minleakage, vmax=maxleakage)
        ax.set_xlabel("RA / pix")
        ax.set_ylabel("Dec / pix")
        cb = plt.colorbar(sc)
        cb.set_label("Fractional leakage / %")
        ax.set_xlim(0, xmax)
        ax.set_ylim(0, ymax)
        ax.set_aspect('equal')
        outpng = f"{obsid}_{subchan}_leakage_map.png" if subchan is not None else f"{obsid}_leakage_map.png"
        fig.savefig(outpng, bbox_inches="tight")

    # Create 3D plot of the data points and the fitted curve
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
    # Reversing these to match that the RA and Dec axes are reversed in the FITS image
        ax.scatter(y, x, z, c=z, vmin=minleakage, vmax=maxleakage)
        x_range = np.linspace(0, xmax, 50)
        y_range = np.linspace(0, ymax, 50)
        Y, X = np.meshgrid(x_range, y_range)
    # Reversing these to match that the RA and Dec axes are reversed in the FITS image
        Z = func((Y, X), *popt)
        ax.plot_surface(Y, X, Z, color='red', alpha=0.5)
        ax.set_xlabel('RA')
        ax.set_ylabel('Dec')
        ax.set_zlabel('Fractional leakage / %')
        outpng = f"{obsid}_{subchan}_leakage_fit.png" if subchan is not None else f"{obsid}_leakage_fit.png"
        fig.savefig(outpng, bbox_inches="tight")

    # Make a residuals plot
        fig = plt.figure()
        ax = fig.add_subplot(111)
    # Reversing these to match that the RA and Dec axes are reversed in the FITS image
        sc = ax.scatter(y, x, c = (z - func((y,x), *popt)), vmin=minleakage, vmax=maxleakage)
        ax.set_xlabel("RA / pix")
        ax.set_ylabel("Dec / pix")
        cb = plt.colorbar(sc)
        cb.set_label("Residual leakage / %")
        ax.set_xlim(0, xmax)
        ax.set_ylim(0, ymax)
        ax.set_aspect('equal')
        outpng = f"{obsid}_{subchan}_corrected_map.png" if subchan is not None else f"{obsid}_corrected_map.png"
        fig.savefig(outpng, bbox_inches="tight")

    return(popt)

def correct_image(Vpb, Ipb, popt, Vout):
    hdu_V = fits.open(Vpb)
    img_V = np.squeeze(hdu_V[0].data)
    xmax, ymax = img_V.shape[0], img_V.shape[1]
    x_range = np.linspace(0, xmax, xmax)
    y_range = np.linspace(0, ymax, ymax)
    Y, X = np.meshgrid(x_range, y_range)
    Z = func((Y, X), *popt)
# Converting from percentage back to fraction
    hdu_V[0].data = np.array(hdu_V[0].data - (1.e-2*Z * np.squeeze(fits.open(Ipb)[0].data)), dtype='float32')
    hdu_V.writeto(Vout, overwrite=True)

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--Inonpb', type=str, dest="Inonpb", help='Stokes I non-primary-beam-corrected image')
    parser.add_argument('--subchan', type=str, dest="subchan", help='The subchannel. Only used for differentiating output plots. If given, the output filename is "{obsid}_{subchan}_leakage_map.png", otherwise "{obsid}_leakage_map.png"')
    parser.add_argument('--Ipb', type=str, dest="Ipb", help='Stokes I primary-beam-corrected image')
    parser.add_argument('--Vpb', type=str, dest="Vpb", help='Stokes V primary-beam-corrected image')
    parser.add_argument('--Vout', type=str, dest="Vout", help='Output leakage-corrected Stokes V image (default _fixed)', default=None)
    parser.add_argument('--nsigma', type=float, default=20, help='Sigma cutoff for source brightness to calculate leakage screen (default=20)')
    parser.add_argument('--plots', action="store_true", default=False, help='Make diagnostic plots (default=False)')
    args = parser.parse_args()

    popt = do_fit(args.Inonpb, args.Ipb, args.Vpb, args.nsigma, args.plots, subchan=args.subchan)
    if args.Vout is not None:
        Vout = args.Vout
    else:
        Vout = args.Vpb.replace('.fits', '_fixed.fits')
    correct_image(args.Vpb, args.Ipb, popt, Vout) 
    
