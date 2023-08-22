#!/usr/bin/env python

import logging
import os

import numpy as np
import astropy.units as u
import matplotlib.pyplot as plt
from astropy.coordinates import match_coordinates_sky, SkyCoord
from astropy.io import fits
from argparse import ArgumentParser
from astropy.table import Table, hstack


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def cross_cata_ggsm(
    cata_tab: Table, ggsm_tab: Table, seplimit=10 * u.arcsecond
) -> Table:
    logger.debug("Creating Skycoord objects")
    cata_sky = SkyCoord(cata_tab["ra"] * u.deg, cata_tab["dec"] * u.deg)
    ggsm_sky = SkyCoord(ggsm_tab["RAJ2000"] * u.deg, ggsm_tab["DEJ2000"] * u.deg)

    logger.info("Cross-matching catalogue to GGSM")
    idx, sep, _ = cata_sky.match_to_catalog_sky(ggsm_sky)

    logger.debug(f"Removing matches greater than {seplimit.to(u.arcsecond)}")
    mask = sep < seplimit

    logger.info(f"Have found {np.sum(mask)} matches")
    idx = idx[mask]
    sep = sep[mask]

    logger.debug("Reordering tables")
    cata_tab = cata_tab[mask]
    ggsm_tab = ggsm_tab[idx]

    logger.debug("Merging tables")
    merge_tab = hstack([cata_tab, ggsm_tab], join_type="exact")

    logger.debug(f"Length of merge table is {len(merge_tab)}")

    return merge_tab


def generate_scale_plot(
    cross_tab: Table, mean_ratio: float, outpath: str, xlabel: str = None
) -> None:
    logger.info(f"Plotting {outpath}")

    xlabel = "Ratios" if xlabel is None else xlabel

    muhat = np.average(
        np.log(cross_tab["int_flux"] / mean_ratio / cross_tab["model_flux"]),
        weights=cross_tab["int_flux"] / cross_tab["err_int_flux"],
    )
    fake_scale2 = np.exp(muhat)

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))

    nbins = int(np.sqrt(len(cross_tab)))

    ax.hist(
        cross_tab["ratio"], bins=nbins, histtype="step", lw=4, label="Original Ratios"
    )
    ax.hist(
        cross_tab["int_flux"] / mean_ratio / cross_tab["model_flux"],
        bins=nbins,
        histtype="step",
        lw=4,
        label="Corrected Ratios",
    )

    ax.axvline(
        mean_ratio, ls="--", lw=3, label=f"{mean_ratio:.2f} - Mean Original Ratio"
    )
    ax.axvline(
        fake_scale2, ls=":", lw=3, label=f"{fake_scale2:.2f} - Mean Corrected Ratio",
    )
    ax.set(xlabel=xlabel, ylabel="Count")

    ax.legend()

    fig.tight_layout()
    fig.savefig(outpath)


def calculate_mean_ratio(
    cross_tab: Table, sigma_thres: float, plot: str = None, pltkwargs: dict = None
) -> float:
    logger.debug(f"Sigma threshold is {sigma_thres}")
    snr = cross_tab["int_flux"] / cross_tab["err_int_flux"]
    mask = (snr > sigma_thres) & (cross_tab["ratio"] > 0)

    logger.debug(f"{np.sum(mask)} sources above minimum S/N threshold")

    muhat = np.average(np.log(cross_tab["ratio"][mask]), weights=snr[mask])
    scale2 = np.exp(muhat)
    logger.info(f"Computed average is {scale2}")

    if plot is not None:
        if pltkwargs is None:
            pltkwargs = {}
        generate_scale_plot(cross_tab[mask], scale2, plot, **pltkwargs)

    return scale2


def write_rescale_outputs(
    image: str, catalogue: str, mean_ratio: float, rmsbkg: bool = False
) -> None:
    logger.info("Creating rescaled data products")

    image_fits_files = [image]
    if rmsbkg is True:
        logger.debug("bkgrms is true. Will apply to BANE products. ")
        image_fits_files.extend(
            [image.replace(".fits", f"_{suf}.fits") for suf in ["bkg", "rms"]]
        )

    if not all(map(os.path.exists, image_fits_files)):
        raise FileNotFoundError("Missing image fits files -- likely rms/bkg related. ")

    for img in image_fits_files:
        logger.debug(f"Rescaling {img}")
        img_out = img.replace(".fits", "_rescaled.fits")

        with fits.open(img) as img_fits:
            logger.debug(f"Creating {img_out}")
            img_fits[0].data /= mean_ratio
            img_fits.writeto(img_out, overwrite=True)

    cols = [
        "int_flux",
        "peak_flux",
        "err_peak_flux",
        "err_int_flux",
        "local_rms",
        "background",
        "residual_mean",
        "residual_std",
    ]

    cata_out = catalogue.replace(".fits", "_rescaled.fits")
    logger.debug(f"Creating {cata_out}")
    logger.debug(f"Opening a fresh copy of {catalogue}")
    cata_rescale = Table.read(catalogue)

    for c in cols:
        logger.debug(f"Rescaling column {c} of {catalogue}")
        cata_rescale[c] /= mean_ratio

    logger.debug(f"Writing out {cata_out}")
    cata_rescale.write(cata_out, overwrite=True)


def derive_apply_scale(
    catalogue: str,
    image: str,
    ggsm: str,
    *args,
    apply: bool = False,
    sigma_thres: float = 25,
    plot: bool = False,
    rmsbkg: bool = False,
    **kwargs,
) -> None:
    logger.debug(f"Opening {image} header")
    img_hdr = fits.getheader(image)
    freq = (img_hdr["FREQ"] * u.hertz).to(u.MHz)

    logger.info(f"Loaded {image} header, and the extracted frequency is {freq}")

    logger.debug(f"Opening {catalogue}")
    cata_tab = Table.read(catalogue)

    logger.debug(f"Opening {ggsm}")
    ggsm_tab = Table.read(ggsm)

    cross_tab = cross_cata_ggsm(cata_tab, ggsm_tab)

    logger.info("Calculating ratios")
    cross_tab["model_flux"] = (
        cross_tab["S_200"] * (freq.value / 200.0) ** cross_tab["alpha"]
    )
    cross_tab["ratio"] = cross_tab["int_flux"] / cross_tab["model_flux"]

    pltkwargs = None
    if plot:
        plotpath = catalogue.replace(".fits", "_rescaled_hist.png")
        pltkwargs = {"xlabel": f"GPM$_{{{freq.value:.0f} \mathrm{{MHz}}}}$/GPM"}

    mean_ratio = calculate_mean_ratio(
        cross_tab, sigma_thres, plot=plotpath, pltkwargs=pltkwargs
    )

    logger.info(f"Mean ratio is {mean_ratio}")

    if not apply:
        logger.info("Not applying the ratio to the data products")
        return
    write_rescale_outputs(image, catalogue, mean_ratio, rmsbkg=rmsbkg)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Rescale a set of images and catalogues based on the average flux offset"
    )

    parser.add_argument(
        "catalogue",
        help="Path to the catalogue to use as the basis to derive the global rescale factor",
        type=str,
    )
    parser.add_argument(
        "image",
        help="Path to the image which will have the global rescale factor applied",
        type=str,
    )
    parser.add_argument(
        "ggsm", help="Path to the GPM global sky model catalogue", type=str,
    )
    parser.add_argument(
        "--apply",
        help="Create new rescaled data products, with the rescaled suffic",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--plot",
        help="Create plots of the before and after the global rescale has been applied",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "--verbose",
        help="Extra logging output (mostly debugging)",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-s",
        "--sigma-thres",
        type=float,
        default=25,
        help="Ignore sources when computing the mean ratio offset below this sigma threshold",
    )
    parser.add_argument(
        "--rmsbkg",
        default=False,
        action="store_true",
        help="Search for and apply the rescaling to the BANE produced RMS and BKG images. ",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    derive_apply_scale(
        args.catalogue,
        args.image,
        args.ggsm,
        apply=args.apply,
        sigma_thres=args.sigma_thres,
        plot=args.plot,
        rmsbkg=args.rmsbkg,
    )

