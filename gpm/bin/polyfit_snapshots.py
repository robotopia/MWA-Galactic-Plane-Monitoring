#!/usr/bin/env python
from __future__ import print_function
from multiprocessing import Pool
from math import ceil

from astropy.time import Time
from astropy.io import fits
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.table import Table
from astropy import wcs
import astropy.units as u

import numpy as np

import os
import sys
import glob

import matplotlib

matplotlib.use("Agg")  # Avoid using the display on supercomputers
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import argparse


def make_plot(x, y, w, model, title, ylabel, outname):
    figsize = (6, 6)
    x = [X for (W, X) in sorted(zip(w, x))]
    y = [Y for (W, Y) in sorted(zip(w, y))]
    w = sorted(w)
    SNR = np.log10(w)
    fitplot = plt.figure(figsize=figsize)
    ax = fitplot.add_subplot(111)
    ax.set_title(title, fontsize=10)
    ax.scatter(x, y, marker=".", c=SNR, cmap="Greys")
    x = sorted(x)
    ax.plot(x, model(x), "-", ms=1)
    ax.set_xlabel(ylabel)
    ax.set_ylabel("log10 ratio")
    ax.set_ylim([-0.1, 0.1])

    print("Saving {0}".format(outname))
    fitplot.savefig(outname, bbox_inches="tight")


def zmodel(x):
    return np.zeros(len(x))


def apply_correction_screen(
    data: np.ndarray, correction: np.ndarray, reshape=None
) -> np.ndarray:
    """A simple function to apply a multiplicative correction screen to the input data. 
    

    Args:
        data (np.ndarray): Image data that needs to be computed
        correction (np.ndarray): Correction factor to apply in a multipilcative pixel-wise manner
        reshape (tuple[int, ...], optional): It not None, the corrected data is cast into this shape. Defaults to None.

    Returns:
        np.ndarray: The corrected data
    """

    corrected_data = data * correction

    if reshape is not None:
        corrected_data = corrected_data.reshape(reshape)

    return corrected_data

    # outformat = "{0},{1},{2},{3}\n"
    # outvars = [obsid, median, peak, std ]
    # outputfile = obsid+"_ionodiff.csv"
    # if not os.path.exists(outputfile):
    #     with open(outputfile, 'w') as output_file:
    #        output_file.write("#obsid,median,peak,std\n")
    #        output_file.write(outformat.format(*outvars))


def sigma_clip(ratios, n=1):
    median = np.median(ratios)
    std = np.nanstd(ratios)
    ind = np.intersect1d(
        np.where(ratios > median - n * std), np.where(ratios < median + n * std)
    )
    return ind


parser = argparse.ArgumentParser()
group1 = parser.add_argument_group("Input files")
group1.add_argument(
    "--filelist",
    dest="filelist",
    default=None,
    help="List of files to use (text file, single column) \
                        Expecting a list of fits files to change, and will \
                        search for associated _comp_matched files with the \
                        source-finding results, and also the <obsid>.metafits",
)
group1.add_argument(
    "--skymodel",
    dest="skymodel",
    default=None,
    help="Sky model to cross-match to (no default)",
)

group2 = parser.add_argument_group("Control options")
group2.add_argument(
    "--nsrc",
    dest="nsrc",
    default=10000,
    type=int,
    help="Number of sources to use for the polynomial fit (default=10000)",
)
group2.add_argument(
    "--threshold",
    dest="SNR_threshold",
    default=None,
    type=int,
    help="Alternatively, set a S/N threshold for sources used for \
                        the polynomial fit (will override --nsrc if set)",
)
group2.add_argument(
    "--order",
    dest="poly_order",
    default=5,
    type=int,
    help="Set the order of the polynomial fit. (default = 5)",
)
group2.add_argument(
    "--ra",
    action="store_true",
    dest="correct_ra",
    default=False,
    help="Measure and correct any RA-offset dependence? (default = False)",
)

group3 = parser.add_argument_group("Creation of output files")
group3.add_argument(
    "--plot",
    action="store_true",
    dest="make_plots",
    default=False,
    help="Make fit plots? (default = False)",
)
group3.add_argument(
    "--rescale",
    action="store_true",
    dest="do_rescale",
    default=False,
    help="Generate rescaled fits files? (default = False)",
)
group3.add_argument(
    "--correctall",
    action="store_true",
    dest="correct_all",
    default=False,
    help="Correct associated background, RMS, and weight maps? (default = False)",
)
group3.add_argument(
    "--overwrite",
    action="store_true",
    dest="overwrite",
    default=False,
    help="Overwrite existing rescaled fits files? (default = False)",
)
group3.add_argument(
    "--read",
    action="store_true",
    dest="read_coefficients",
    default=False,
    help="Read coefficients from file? (default = False)",
)
group3.add_argument(
    "--write",
    action="store_true",
    dest="write_coefficients",
    default=False,
    help="Write coefficients to file? (default = False)",
)
group3.add_argument(
    "-f",
    "--filtered",
    action="store_true",
    default=False,
    help="Included 'filtered' as part of the suffix to denote products are free from bad ionosphere observations",
)
results = parser.parse_args()

if results.filtered:
    print("Will be created the 'filtered' variety of data products. ")
    outsuf = "_filtered"
else:
    outsuf = ""

if os.path.exists(results.filelist):
    f = open(results.filelist, "r+")
    infiles = [line.rstrip() for line in f.readlines()]
    f.close()

    concat_table = results.filelist.replace(".txt", f"_concat{outsuf}.fits")
    title = results.filelist.replace(".txt", "")
    dec_plot = results.filelist.replace(".txt", f"_fitted_dec_poly{outsuf}.png")
    dec_corrected_plot = results.filelist.replace(".txt", "_corrected_dec_poly.png")

    if results.correct_ra is True:
        ra_plot = results.filelist.replace(".txt", f"_fitted_ra_poly{outsuf}.png")
        ra_corrected_plot = results.filelist.replace(
            ".txt", f"_corrected_ra_poly{outsuf}.png"
        )

    # TODO: Replace these with database calls?
    if results.write_coefficients is True or results.read_coefficients is True:
        dec_coeff = results.filelist.replace(".txt", f"_dec_coefficients{outsuf}.csv")
        if results.correct_ra is True:
            ra_coeff = results.filelist.replace(".txt", f"_ra_coefficients{outsuf}.csv")
else:
    print(results.filelist)
    print("Must specify a list of files to read!")
    sys.exit(1)


if results.read_coefficients is True:
    P_dec = np.loadtxt(dec_coeff, delimiter=",")
    decmodel = np.poly1d(P_dec)
    if results.correct_ra is True:
        P_ra = np.loadtxt(ra_coeff, delimiter=",")
        ramodel = np.poly1d(P_ra)

else:
    logratios = np.empty(0)
    int_fluxes = np.empty(0)
    local_rmses = np.empty(0)
    S200s = np.empty(0)
    alphas = np.empty(0)
    ras = np.empty(0)
    ra_offs = np.empty(0)
    decs = np.empty(0)

    obsids = []

    for fitsimage in infiles:
        sf = fitsimage.replace(".fits", "_comp.fits")
        sfm = fitsimage.replace(".fits", f"_comp_matched{outsuf}.fits")

        # Cross-match with a sky model to get model flux densities
        if not os.path.exists(sfm):
            # Rely on the user running Aegean and just fail if the source-finding isn't there
            if not os.path.exists(sf):
                print("Source-finding results for {0} not found".format(fitsimage))
                sys.exit(1)

            os.system(
                'stilts tmatch2 \
            values1="RAJ2000 DEJ2000" \
            values2="ra dec" \
            in1={0} in2={1} \
            matcher=sky params=45 \
            out={2}'.format(
                    results.skymodel, sf, sfm
                )
            )
        gpstime = Time(int(fitsimage[0:10]), format="gps")

        # We get this from the FITS image rather than the metafits because I make sub-band images
        hdr = fits.getheader(fitsimage)
        centfreq = hdr["CRVAL3"] / 1.0e6  # MHz

        # But the metafits is better for the RA, because of the denormal projection
        path, _ = os.path.split(fitsimage)
        metafits = glob.glob("{0}/{1}*metafits*".format(path, fitsimage[0:10]))
        metafits = metafits[0]
        meta = fits.getheader(metafits)
        ra_cent = meta["RA"]

        # Get the cross-matched catalogue
        hdu = fits.open(sfm)
        cat = hdu[1].data

        obsids.extend([fitsimage[:10] for _ in range(len(cat))])

        # RA offsets and Decs
        ras = np.append(ras, cat["RAJ2000"])
        ra_offs = np.append(
            ra_offs, cat["RAJ2000"] - ra_cent * np.ones(len(cat["RAJ2000"]))
        )
        decs = np.append(decs, cat["DEJ2000"])

        # Flux densities
        int_fluxes = np.append(int_fluxes, cat["int_flux"])
        S200s = np.append(S200s, cat["S_200"])
        alphas = np.append(alphas, cat["alpha"])
        logratios = np.append(
            logratios,
            np.log10(
                cat["S_200"] * (centfreq / 200.0) ** cat["alpha"] / cat["int_flux"]
            ),
        )
        local_rmses = np.append(local_rmses, cat["local_rms"])

    # sigma-clip to get rid of crazy values
    ind = sigma_clip(logratios, 3)
    median = np.median(logratios[ind])
    std = np.nanstd(logratios[ind])
    vmin = median - std
    vmax = median + std

    h = ra_offs[ind]
    a = ras[ind]
    d = decs[ind]
    c = logratios[ind]
    f = int_fluxes[ind]
    r = local_rmses[ind]
    S200 = S200s[ind]
    alpha = alphas[ind]
    obsids = [obsids[i] for i in ind]

    # Get the highest S/N measurements
    if results.SNR_threshold is None:
        SNR = sorted(f / r, reverse=True)
        threshold = SNR[results.nsrc]
    else:
        threshold = results.SNR_threshold

    good = np.where(f / r > threshold)

    P, res, rank, sv, cond = np.polyfit(
        np.array(d[good]),
        np.array(c[good]),
        results.poly_order,
        full=True,
        w=f[good] / r[good],
    )
    decmodel = np.poly1d(P)

    # Remove outliers
    model_subtracted = c[good] - decmodel(d[good])
    indices = sigma_clip(model_subtracted, 3)

    # Re-fit model
    P_dec, res, rank, sv, cond = np.polyfit(
        np.array(d[good][indices]),
        np.array(c[good][indices]),
        results.poly_order,
        full=True,
        w=f[good][indices] / r[good][indices],
    )
    decmodel = np.poly1d(P_dec)

    if results.write_coefficients is True:
        np.savetxt(
            dec_coeff,
            P_dec,
            delimiter=",",
            header="Order-{0} polynomial fit coefficients".format(results.poly_order),
        )

    # Now that we have accumulated Dec, apply the polynomials to the concatenated catalogue, and then fit over RA
    new_int_fluxes = int_fluxes * 10 ** (decmodel(decs))
    new_logratios = np.log10(S200s * (centfreq / 200.0) ** alphas / new_int_fluxes)

    new_f = new_int_fluxes[ind]
    new_c = new_logratios[ind]

    if results.correct_ra is True:
        P_ra, res, rank, sv, cond = np.polyfit(
            np.array(h[good]),
            np.array(new_c[good]),
            results.poly_order,
            full=True,
            w=f[good] / r[good],
        )
        ramodel = np.poly1d(P_ra)

        model_subtracted = new_c[good] - ramodel(h[good])
        indices = sigma_clip(model_subtracted, 3)

        # Re-fit model
        P_ra, res, rank, sv, cond = np.polyfit(
            np.array(h[good][indices]),
            np.array(new_c[good][indices]),
            results.poly_order,
            full=True,
            w=f[good][indices] / r[good][indices],
        )
        ramodel = np.poly1d(P_ra)
        if results.write_coefficients is True:
            np.savetxt(
                ra_coeff,
                P_ra,
                delimiter=",",
                header="Order-{0} polynomial fit coefficients".format(
                    results.poly_order
                ),
            )

        final_int_fluxes = new_int_fluxes * 10 ** (ramodel(ra_offs))
        final_logratios = np.log10(
            S200s * (centfreq / 200.0) ** alphas / final_int_fluxes
        )

        final_f = final_int_fluxes[ind]
        final_c = final_logratios[ind]
    else:
        final_c = new_c
        final_f = new_f

    print("Length of h: ", len(h))
    print("Length of obsids: ", len(obsids))

    # Save the results as a FITS table
    t = Table(
        [h, a, d, f, new_f, final_f, r, S200, alpha, c, new_c, final_c, obsids],
        names=(
            "RA_offset",
            "RA",
            "Dec",
            "flux",
            "flux_after_dec_corr",
            "flux_after_full_corr",
            "local_rms",
            "S_200",
            "alpha",
            "log10ratio",
            "log10ratio_after_dec_corr",
            "log10ratio_after_full_cor",
            "original_obsid",
        ),
    )
    t.write(concat_table, overwrite=True)

    # TODO Fix the plotting so it can be run even if the coefficients and sources are read in from a table
    # Likely to do this I will need to add a new column to the table that says whether a source was used for fitting
    if results.make_plots is True:
        # Weights for plotting
        w = f[good][indices] / r[good][indices]

        # Dec plot
        x = d[good][indices]
        y = c[good][indices]
        make_plot(x, y, w, decmodel, title, "Declination (deg)", dec_plot)

        # Dec plot after Dec correction
        y = new_c[good][indices]
        make_plot(x, y, w, zmodel, title, "Declination (deg)", dec_corrected_plot)

        if results.correct_ra is True:
            # RA plot after Dec correction
            x = h[good][indices]
            y = new_c[good][indices]
            make_plot(x, y, w, ramodel, title, "RA offset (deg)", ra_plot)

            # RA plot after RA (and Dec) correction
            y = final_c[good][indices]
            make_plot(x, y, w, zmodel, title, "RA offset (deg)", ra_corrected_plot)

if results.do_rescale is True:

    # Create a cache for correction screens with the same image size
    corr = {}

    for item, fitsimage in enumerate(infiles):
        print("{0} of {1}) {2}".format(item + 1, len(infiles), fitsimage))
        if results.correct_all is True:
            extlist = ["", "_bkg", "_rms", "_weight", "_comp"]
        else:
            extlist = [""]

        for ext in extlist:
            infits = fitsimage.replace(".fits", ext + ".fits")
            outfits = infits.replace(
                ext + ".fits", f"_rescaled{outsuf}" + ext + ".fits"
            )

            if (not os.path.exists(outfits)) or results.overwrite is True:
                print("Creating {0} from {1}".format(outfits, infits))
                # Modify each fits file to produce a new version
                hdu_in = fits.open(infits)
                if hdu_in[0].data is None:
                    # Then it is a source-finding catalogue not an image
                    cat = hdu_in[1].data
                    dec = cat["dec"]
                    dec_corr = np.zeros(dec.shape)
                    ra_corr = np.zeros(ra.shape)
                    # We generated log10 ratios so use 10^ to get back to raw correction
                    # e.g. a 4th order polynomial would look like:
                    # corr = 10** ( a*(Dec)^3 + b*(Dec)^2 + c*Dec + d)
                    for i in range(0, results.poly_order + 1):
                        dec_corr += P_dec[i] * pow(dec, results.poly_order - i)
                    dec_corr = 10 ** dec_corr
                    # Obviously only modify columns which use the flux density
                    cols = [
                        "background",
                        "local_rms",
                        "peak_flux",
                        "err_peak_flux",
                        "int_flux",
                        "err_int_flux",
                        "residual_mean",
                        "residual_std",
                    ]
                    for col in cols:
                        cat[col] *= dec_corr

                    if results.correct_ra is True:
                        for i in range(0, results.poly_order + 1):
                            ra_corr += P_ra[i] * pow(
                                ra - ra_cent, results.poly_order - i
                            )
                        ra_corr = 10 ** ra_corr
                        for col in cols:
                            cat[col] *= ra_corr

                    print("Creating {0}".format(outfits))

                    hdu_in.writeto(outfits, overwrite=True)
                    hdu_in.close()
                else:
                    # This is an image not a source-finding catalogue
                    # wcs in format [stokes,freq,y,x]; stokes and freq are length 1 if they exist
                    w = wcs.WCS(hdu_in[0].header, naxis=2)
                    naxes = hdu_in[0].header["NAXIS"]

                    # going to need the RA in order to calculate the RA offsets
                    path, fl = os.path.split(infits)
                    metafits = glob.glob("{0}/{1}*metafits*".format(path, fl[0:10]))
                    metafits = metafits[0]
                    meta = fits.getheader(metafits)
                    ra_cent = meta["RA"]
                    if naxes == 4:
                        m, n = 2, 3
                    elif naxes == 2:
                        m, n = 0, 1

                    img_shape = hdu_in[0].data.shape

                    # Derive the correction screen once, and use it for all
                    # image based fits files
                    if img_shape not in corr.keys():
                        print(f"Calculation correction screen for shape {img_shape}")

                        # create an array but don't set the values (they are random)
                        indexes = np.empty(
                            (hdu_in[0].data.shape[m] * hdu_in[0].data.shape[n], 2),
                            dtype=int,
                        )
                        idx = np.array([(j, 0) for j in range(hdu_in[0].data.shape[n])])
                        j = hdu_in[0].data.shape[n]
                        for i in range(hdu_in[0].data.shape[m]):
                            idx[:, 1] = i
                            indexes[i * j : (i + 1) * j] = idx

                        # put ALL the pixels into our vectorized functions and minimise our overheads
                        ra, dec = w.wcs_pix2world(indexes, 1).transpose()
                        dec_corr = np.zeros(dec.shape)
                        ra_corr = np.zeros(ra.shape)

                        for i in range(0, results.poly_order + 1):
                            dec_corr += P_dec[i] * pow(dec, results.poly_order - i)
                        dec_corr = 10 ** dec_corr

                        if results.correct_ra is True:
                            for i in range(0, results.poly_order + 1):
                                ra_corr += P_ra[i] * pow(
                                    ra - ra_cent, results.poly_order - i
                                )
                            ra_corr = 10 ** ra_corr
                            corr_apply = dec_corr * ra_corr

                        else:
                            corr_apply = dec_corr

                        corr_apply = corr_apply.reshape(
                            hdu_in[0].data.shape[m], hdu_in[0].data.shape[n]
                        )
                        print(f"Caching correction screen for {img_shape}")
                        corr[img_shape] = corr_apply

                    hdu_in[0].data = np.array(
                        corr[img_shape] * hdu_in[0].data, dtype=np.float32
                    )

                    hdu_in.writeto(outfits, overwrite=True)
                    hdu_in.close()
