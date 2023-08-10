#!/usr/bin/env python

# Make plots for the candidate 5-minute timescale transients

from astropy.time import Time
from astropy.io import fits
from matplotlib import pyplot as plt
import numpy as np
from astropy import wcs
from astropy.nddata import Cutout2D
from astropy import units as u
from astropy.coordinates import SkyCoord

import argparse

def plot(ra, dec, fits_det, fits_non, cand, size=0.25):

    framesize = u.Quantity(size, u.deg)
    location = SkyCoord(ra, dec, unit=(u.deg, u.deg))

    hdu_det = fits.open(fits_det)
    data_det = np.squeeze(hdu_det[0].data)
    w_det = wcs.WCS(hdu_det[0].header, naxis=2)
    cutout_det = Cutout2D(data_det, location, framesize, wcs=w_det)

    hdu_non = fits.open(fits_non)
    data_non = np.squeeze(hdu_non[0].data)
    w_non = wcs.WCS(hdu_non[0].header, naxis=2)
    cutout_non = Cutout2D(data_non, location, framesize, wcs=w_non)

    vmin = np.nanmin([np.nanmin(cutout_det.data), np.nanmin(cutout_non.data)])
    vmax = np.nanmax([np.nanmax(cutout_det.data), np.nanmax(cutout_non.data)])

    fig = plt.figure(figsize=(12,6))
    ax1 = fig.add_axes([0.1,0.1,0.3,0.6], projection=cutout_det.wcs)
    ax2 = fig.add_axes([0.46,0.1,0.3,0.6], projection=cutout_non.wcs)
    cax = fig.add_axes([0.77,0.1,0.015,0.6])
    im1 = ax1.imshow(cutout_det.data, origin='lower', vmin=vmin, vmax=vmax, cmap='gray')
    im2 = ax2.imshow(cutout_non.data, origin='lower', vmin=vmin, vmax=vmax, cmap='gray')
    cbar = plt.colorbar(im1, cax=cax, label='Jy/beam')
    ax1.set_title(f'Detection: {fits_det[0:10]}')
    ax2.set_title(f'Non-detection: {fits_non[0:10]}')
    ax1.set_xlabel('RA')
    ax1.set_ylabel('Dec')
    ax2.set_xlabel('RA')
    ax2.set_ylabel(' ')
    ax2.set_yticks([])
    plt.setp(ax2.get_yticklabels(), visible=False)

    fig.savefig(f'{cand}.png', bbox_inches='tight')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", dest='table', type=str, default=None,
                        help="A concatenated table of candidates.")
    args = parser.parse_args()

    tab = fits.open(args.table)[1].data
    for row in tab:
        obs_det = row['detectedin']
        obs_non = row['undetectedin']
        fits_det = f'{obs_det}/{obs_det}_deep-MFS-image-pb_warp.fits'
        fits_non = f'{obs_non}/{obs_non}_deep-MFS-image-pb_warp.fits'
        plot(row['ra'], row['dec'], fits_det, fits_non, row['uuid'])
