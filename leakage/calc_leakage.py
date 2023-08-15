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

def make_plots(Inonpb, Ipb, Vpb, nsigma=20):

    obsid = Inonpb[0:10]

    img_I_npb = np.squeeze(fits.open(Inonpb)[0].data)
    img_I = np.squeeze(fits.open(Ipb)[0].data)
    img_V = np.squeeze(fits.open(Vpb)[0].data)

    cdelt = fits.open(Inonpb)[0].header["CDELT2"]
    xmax, ymax = img_I.shape[0], img_I.shape[1]
    ind = np.indices(img_I.shape)
 
    x, y = ind[0], ind[1]
    mid = x[0].shape[0] / 2
#    dist = cdelt*np.sqrt((x - mid)**2 + (y - mid)**2)

    # Make a box of the inside 1/3rd of the image where hopefully we're artefact-free
    imsize = img_I.shape[0]
    l = int(np.round(imsize/3))
    r = imsize - l

    # Not worth looking at anything under some brightness (use sigma-clipping to find rms)
    img_I[img_I_npb < nsigma*scstd(img_I_npb[l:r,l:r])] = np.nan
    frac = np.abs(img_V / img_I)

#    fig = plt.figure()
#    ax = fig.add_subplot(111)
#    ax.scatter(np.ndarray.flatten(dist[~np.isnan(frac)]), 1.e2*np.ndarray.flatten(frac[~np.isnan(frac)]))#, alpha=np.ndarray.flatten(normalize_2d(img_I[~np.isnan(frac)])))
#    ax.set_xlabel("Distance from boresight / deg")
#    ax.set_ylabel("Fractional leakage / %")
    #ax.set_xscale("log")
    #ax.set_yscale("log")
    #ax.set_ylim(0.01, 2)
#    fig.savefig("fractional_leakage.png")

    x = x[~np.isnan(frac)]
    y = y[~np.isnan(frac)]
    z = 1.e2*np.ndarray.flatten(frac[~np.isnan(frac)])

    minleakage = np.nanmin(z)
    maxleakage = np.nanmax(z)

    fig = plt.figure()
    ax = fig.add_subplot(111)
    sc = ax.scatter(x, y, c=z, vmin=minleakage, vmax=maxleakage)
    ax.set_xlabel("RA / pix")
    ax.set_ylabel("Dec / pix")
    cb = plt.colorbar(sc)
    cb.set_label("Fractional leakage / %")
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_aspect('equal')
    fig.savefig(f"{obsid}_leakage_map.png", bbox_inches="tight")

# Perform curve fitting
    popt, pcov = curve_fit(func, (x, y), z)

# Create 3D plot of the data points and the fitted curve
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.scatter(x, y, z, c=z, vmin=minleakage, vmax=maxleakage)
    x_range = np.linspace(0, xmax, 50)
    y_range = np.linspace(0, ymax, 50)
    X, Y = np.meshgrid(x_range, y_range)
    Z = func((X, Y), *popt)
    ax.plot_surface(X, Y, Z, color='red', alpha=0.5)
    ax.set_xlabel('RA')
    ax.set_ylabel('Dec')
    ax.set_zlabel('Fractional leakage / %')
    fig.savefig(f"{obsid}_leakage_fit.png", bbox_inches="tight")

# Make a residuals plot
    fig = plt.figure()
    ax = fig.add_subplot(111)
    sc = ax.scatter(x, y, c=z/func((x,y), *popt), vmin=minleakage, vmax=maxleakage)
    ax.set_xlabel("RA / pix")
    ax.set_ylabel("Dec / pix")
    cb = plt.colorbar(sc)
    cb.set_label("Residual leakage / %")
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_aspect('equal')
    fig.savefig(f"{obsid}_corrected_map.png", bbox_inches="tight")

    return(func)

def correct_image(Vpb, func, Vout):
    img_V = np.squeeze(fits.open(Vpb)[0].data)
    xmax, ymax = img_V.shape[0], img_V.shape[1]
    x_range = np.linspace(0, xmax)
    y_range = np.linspace(0, ymax)
    X, Y = np.meshgrid(x_range, y_range)
    Z = func((X, Y), *popt)
    hdu[0].data /= Z
    hdu.writeto(Vout, overwrite=True)
   

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--Inonpb', type=str, dest="Inonpb", help='Stokes I non-primary-beam-corrected image')
    parser.add_argument('--Ipb', type=str, dest="Ipb", help='Stokes I primary-beam-corrected image')
    parser.add_argument('--Vpb', type=str, dest="Vpb", help='Stokes V primary-beam-corrected image')
    parser.add_argument('--Vout', type=str, dest="Vout", help='Output leakage-corrected Stokes V image (default _fixed)', default=None)
    parser.add_argument('--nsigma', type=float, default=20, help='Sigma cutoff for source brightness to calculate leakage screen (default=20)')
#    parser.add_argument('--cutoff', default=None, type=float, help='Cutoff value for island detection')
    #parser.add_argument('--std', default=False, help='Use standard deviation for cutoff', action=argparse.BooleanOptionalAction)
#    parser.add_argument('--std', default=False, help='Use standard deviation for cutoff', action="store_true")
#    parser.add_argument('--peak-name', default='peak_val', type=str, help='Column name of peak value in island')
#    parser.add_argument('--filter-name', default='unknown_filter', type=str, help='Name of filter')
    args = parser.parse_args()

    func = make_plots(args.Inonpb, args.Ipb, args.Vpb, args.nsigma)
    if args.Vout is not None:
        Vout = args.Vout
    else:
        Vout = args.Vpb.replace('.fits', '_fixed.fits')
    correct_image(args.Vpb, func, Vout) 
    
