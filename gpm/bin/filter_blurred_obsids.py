#! /usr/bin/env python

"""A script to identify the typical blurring of sources across a collection of obsids, and then 
filter out the obsids with excess bluring. This assumes that the rescale and mosaic tasks have 
already been executed, as the input data products are the concatenated source catalogue of all
individual obsids, and the projpsf_psf.fits image that is produced by mosaic.tmpl

As output to the script is a new text file of obsids that are worthy of being re-processed
"""
import logging
from argparse import ArgumentParser
from typing import Dict, Union
from os.path import basename

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import astropy.units as u
from astropy.table import Table
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS
from astropy.wcs.utils import skycoord_to_pixel
from astropy.io import fits

from gpm.utils.obsid_ops import write_obsids_file


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


def _get_blur_slice(projpsf: str) -> Union[WCS, np.ndarray]:
    """Opens the projected psf fits image and extracts the blur plane

    Args:
        projpsf (str): Path to the projected psf image

    Returns:
        Union[WCS, np.ndarray]: The WCS and the blur plan of the projected PSF fits cube
    """
    logger.debug(f"Reading {projpsf}")
    with fits.open(projpsf) as psf_fits:
        psf_wcs = WCS(psf_fits[0])
        psf_blur = psf_fits[0].data[3]

    return psf_wcs, psf_blur


def _read_clean_table(src_cata: str) -> pd.DataFrame:
    """Reads in and returns the concatentated source catalogue produced
    by a previous drift_rescale command. This function does not automatically
    deduce any path or other meta data

    Args:
        src_cata (str): Path to the concatenated fits table

    Returns:
        pd.DataFrame: Concatenated source table with cleaned data
    """
    logger.debug(f"Reading {src_cata}")
    src_cata = Table.read(src_cata).to_pandas()
    src_cata["original_obsid"] = src_cata["original_obsid"].str.decode("utf-8")

    return src_cata


def _derive_frequency(projpsf_path: str) -> float:
    """Estimate the observed frequency given the filename of the projected PSF cube

    Args:
        projpsf_path (str): Filename of the projected PSF cube produced with typical GPM pipeline processing

    Returns:
        float: Frequency in MHz
    """

    # Only way I can think of reliably getting the frequency of mosaic out without
    # too much pain _in this script_ is to scrap it out of the filename.
    logger.debug(f"projpsf path is {projpsf_path}")
    name = [i for i in basename(projpsf_path).split("_") if "MHz" in i]
    logger.debug(f"Extracted name is {name}")

    assert len(name) == 1, f"No frequency information found in {projpsf_path}"

    freq = np.mean([float(f) for f in name[0].replace("MHz", "").split("-")])
    logger.info(f"Detected frequency of {freq}")

    return freq


def _get_blur_limits(
    src_cata_path: str, projpsf_path: str, thres: float = None, diff: float = None
) -> Dict[str, float]:
    """Returns the typical filtering parameters given the frequency of the observation

    Args:
        projpsf_path (str): Filename of the projected PSF cube produced with typical GPM pipeline processing

    Keyword Args:
        thres (float): The absolute threshold limit. If None, use the the value hardcoded for each frequency. Defaults to None. 
        diff (float): The acceptable inter-quartile difference limit. If None, use the the value hardcoded for each frequency. Defaults to None. 

    Returns:
        Dict[str, float]: The `threshold` and `diff` to use
    """

    freq = _derive_frequency(projpsf_path)

    if freq < 100:
        val = [1.25, 0.1]
    elif freq < 134:
        val = [1.2, 0.1]
    else:
        val = [1.15, 0.1]

    if thres is not None:
        logger.info(f"Setting user threshold of {thres}")
        val[0] = thres
    if diff is not None:
        logger.info(f"Setting user difference limit of {diff}")
        val[1] = diff

    logger.debug(f"Adopted filter threshold values are {val}")
    return {"threshold": val[0], "diff": val[1]}


def plot_blur_time(
    src_desc: pd.DataFrame, mask: np.ndarray, params: Dict[str, float], outpath: str
):
    """Produce simple diagnostic plots of the time-varying blur factors

    Args:
        src_desc (pd.DataFrame): Result of a pd.DataFrame.groupby)_.describe() process
        mask (np.ndarray): Boolean mask of the bad obsids that are going to be filtered out
        params (Dict[str, float]): Filtering parameters derived based on frequency. Must have `threshold` and `diff` attributes
        outpath (str): Location to write plot to
    """
    logger.info(f"Creating {outpath}")
    markers = np.array([int(a) for a in src_desc.index.values])

    fig, ax = plt.subplots(1, 1)

    ax.plot(markers - np.min(markers), src_desc["blur_val"]["mean"], color="blue")
    ax.fill_between(
        markers - np.min(markers),
        src_desc["blur_val"]["25%"],
        src_desc["blur_val"]["75%"],
        color="blue",
        alpha=0.4,
        label="Interquartile",
    )

    ax.axhline(params["threshold"], ls="--", color="black")
    ax.plot(
        markers[mask] - np.min(markers),
        src_desc["blur_val"]["mean"][mask],
        "ro",
        label="Bad obsids",
    )

    ax.set(
        xlabel="Normalised Obsid",
        ylabel="Mean Blur Value",
        title=f"{np.sum(mask)} obsids flagged",
        ylim=[0.9, 1.5],
    )

    ax.legend()

    fig.tight_layout()
    fig.savefig(outpath)


def filter_blurred_obsids(
    src_cata: pd.DataFrame,
    filter_params: Dict[str, float],
    obsid_col: str = "original_obsid",
    plot: Union[str, None] = None,
):
    """Filter out obsids that have been detected to have too much blurring, indicative of 
    bad ionosphere

    Args:
        src_cata (pd.DataFrame): Path to concatenated source catalogue produced by drift_rescale
        filter_params (Dict[str, float]): Parameters used to make obsids as bad. Must have `threshold` and `diff` keys
        obsid_col (str, optional): The obsid column stored in the `src_cata` file. Defaults to "original_obsid".
        plot (str, optional): Perform plotting visualisation and save results to this path. If None dont perform. Defaults to None.

    Returns:
        Uniona[np.ndarray,np.ndarray]: A boolean mask of equal length to `src_cata` of bad obsid (after a .groupby().describe()),
        and a list of good obsids that are not flagged
    """
    logger.debug(f"Filtering blurred obsids")
    desc = src_cata.groupby(obsid_col).describe()
    mask = desc["blur_val"]["mean"] > filter_params["threshold"]
    mask = mask | (
        (desc["blur_val"]["75%"] - desc["blur_val"]["25%"]) > filter_params["diff"]
    )
    logger.info(f"{len(mask)} unique obsids")
    logger.info(f"{np.sum(mask)} flagged as bad")

    if plot is not None:
        plot_blur_time(desc, mask, filter_params, plot)

    good_obsids = desc.index.values[~mask]

    return mask, good_obsids


def blur_filter_obsids(
    src_cata_path: str,
    projpsf_path: str,
    outpath_obsid: str,
    plot: Union[bool, None] = False,
    thres: float = None,
    diff: float = None,
):
    """Identify obsids that are considered bad and flag them out. Only good obsids are written to a
    specified file. 

    Args:
        src_cata_path (str): Path to concatenated source catalogue produced by a previous drift_rescale
        projpsf_path (str): Path to a projpsf_psf.fits file produced by a provious drift_mosaic
        outpath_obsid (str): Output path to write the set of good obsids to
        plot (bool, optional): Create simple visualisations of the blurring across obsids. Defaults to False.
    
    Keyword Args:
        thres (float): The absolute threshold limit. If None, use the the value hardcoded for each frequency. Defaults to None. 
        diff (float): The acceptable inter-quartile difference limit. If None, use the the value hardcoded for each frequency. Defaults to None. 

    """
    # Read in table and convert to skycoord object
    src_cata = _read_clean_table(src_cata_path)
    src_sky = SkyCoord(src_cata.RA, src_cata.Dec, unit=(u.deg, u.deg))

    # Read in the projected psf cube and create wcs object
    psf_wcs, psf_blur = _get_blur_slice(projpsf_path)

    # Get all the blur factors
    logger.debug(f"Converting skycoordinates to pixel positions and evaluating")
    src_pix = skycoord_to_pixel(src_sky, psf_wcs)
    src_cata["blur_val"] = psf_blur[
        src_pix[1].astype(int), src_pix[0].astype(int)
    ].astype("f8")

    # Get the filter specifications
    params = _get_blur_limits(src_cata_path, projpsf_path, thres=thres, diff=diff)
    plot_path: Union[str, None] = src_cata_path.replace(
        ".fits", "_flagged.png"
    ) if plot else None
    obsid_mask, good_obsids = filter_blurred_obsids(src_cata, params, plot=plot_path)

    if outpath_obsid is not None:
        write_obsids_file(good_obsids, outpath_obsid)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Filter out obsids whose sources have excessive blur factors"
    )
    parser.add_argument(
        "concat_catalogue",
        help="The concatenated catalogue produced from a previous invocation of drift_rescale",
    )
    parser.add_argument(
        "projpsf",
        help="The projected PSF cube produced from a previous invocation of drift_mosaic",
    )
    parser.add_argument(
        "outpath_obsid", help="Output text file to place good obsids into"
    )
    parser.add_argument(
        "-p",
        "--plot",
        help="Create simple diagnostic plots",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Enable extra output when running",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        default=None,
        type=float,
        help="The absolute threshold of the average blur factor in an obsid before it is marked as bad. ",
    )
    parser.add_argument(
        "-d",
        "--difference",
        default=None,
        type=float,
        help="The absolute threshold of the inter-quartile range of the blur factor in an obsid before it is marked as bad. ",
    )

    args = parser.parse_args()

    if args.verbose is True:
        logger.setLevel(logging.DEBUG)

    blur_filter_obsids(
        args.concat_catalogue,
        args.projpsf,
        args.outpath_obsid,
        plot=args.plot,
        thres=args.threshold,
        diff=args.difference,
    )

