#! /usr/bin/env python

import logging
from os import read
from astropy.units.equivalencies import pixel_scale
import numpy as np
import astropy.units as u
from astropy.wcs import WCS
from astropy.io import fits
from astropy.stats.circstats import circmean
from astropy.coordinates import SkyCoord
from argparse import ArgumentParser
from typing import Iterable, Union, Tuple
from gpm.utils.obsid_ops import read_obsids_file

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

def generate_zea_wcs(cen_ra: float, cen_dec: float):
    """Generates a small ZEA template at the approximate location of the center of 
    observations. This is use to later refine the central position

    Args:
        cen_ra (float): The RA position in degrees of the reference pixel
        cen_dec (float): The Dec position in degrees of the reference pixel
    """
    logger.debug("Creating the ZEA WCS instance")

    pixscale = 1
    wcs_info = {
        'naxis':2, 
        'crpix1':int(cen_ra),
        'crpix2':int(cen_dec)+90,
        'crval1':cen_ra,
        'crval2':cen_dec,
        'cd1_1': -pixscale,
        'cd1_2': 0,
        'cd2_1': 0,
        'cd2_2': pixscale,
        'ctype1': 'RA---ZEA',
        'ctype2': 'DEC--ZEA',
        'naxis1': 360,
        'naxis2': 180
    }

    return WCS(wcs_info)

def zea_centre(ras: Iterable[float], decs: Iterable[float], mean_pos: Tuple[float, float]) -> Tuple[float, ...]:

    mean_ra, mean_dec = mean_pos 

    zea_wcs = generate_zea_wcs(mean_ra, mean_dec)

    logger.debug("Converting sky coordinates to pixels")
    pix = zea_wcs.all_world2pix(ras*u.deg, decs*u.deg, 0)
    
    logger.debug("Identifying limits in pixel space")
    min_ra_pix, max_ra_pix = np.min(pix[0]), np.max(pix[0])
    min_dec_pix, max_dec_pix = np.min(pix[1]), np.max(pix[1])

    logger.debug('Calculating the centre of the limits')
    mean_ra_pix = np.mean((min_ra_pix, max_ra_pix))
    mean_dec_pix = np.mean((min_dec_pix, max_dec_pix))

    logger.debug(f"Converting {mean_ra_pix} {mean_dec_pix} pixels to the sky")
    zea_mean_ra, zea_mean_dec = zea_wcs.all_pix2world(mean_ra_pix, mean_dec_pix, 0)

    return tuple([float(zea_mean_ra), float(zea_mean_dec)])

def filter_files_from_obsid(
    files: Iterable[str], obsids: Iterable[int]
) -> Iterable[str]:
    """Given a set of file paths (assuming GPM directories) and a set of obsids, filter
    out all paths that do not have an obsid beloning to the set of obsids. 

    Args:
        files (Iterable[str]): List of files to filter out
        obsids (Iterable[int]): List of acceptable obsids

    Returns:
        Iterable[str]: Path to files whose obsid is included in the obsid set
    """
    filter_files = []
    for f in files:
        for obsid in obsids:
            if str(obsid) in f:
                filter_files.append(f)
                break

    return filter_files


def calculate_mean(
    files: Iterable[str],
    print_pos: bool = False,
    filter_obsids: str = None,
    ra_field: str = "CRVAL1",
    dec_field: str = "CRVAL2",
    refine_position: bool = False
) -> Union[float, float]:
    """Calculate the mean position based on RA/Dec values extracted from a set of FITS files

    Args:
        files (Iterable[str]): FITS files to process
        print_pos (bool, optional): Output results to stdout. Defaults to False.
        filter_obsids (str, optional): Path to standard GPM obsids text file (new line delimited). Defaults to None.
        ra_field (str, optional): RA field in FITS header. Defaults to "CRVAL1".
        dec_field (str, optional): Dec field in FITS header. Defaults to "CRVAL2".

    Returns:
        Union[float, float]: Mean RA and Dec position
    """

    if filter_obsids is not None:
        logger.debug(f"Number of input files: {len(files)}")

        obsids = read_obsids_file(filter_obsids)
        logger.debug(f"Number of obsids to include: {len(obsids)}")

        files = filter_files_from_obsid(files, obsids)
        logger.debug(f"Number of valid files: {len(files)}")

    positions = []
    for file in files:
        with fits.open(file, mode="readonly", memmap=True) as in_fits:
            if ra_field not in in_fits[0].header:
                logger.debug(f"{ra_field} not in {file}")
                continue
            if dec_field not in in_fits[0].header:
                logger.debug(f"{dec_field} not in {file}")
                continue

            try:
                ra = in_fits[0].header[ra_field]
                dec = in_fits[0].header[dec_field]

                positions.append((file, ra, dec))
            except:
                logger.warn(f"Position could not be read for {file}")

    if len(positions) == 0:
        logger.debug("No positions were captured. ")
        return np.nan, np.nan

    ras = [i[1] for i in positions]
    decs = [i[2] for i in positions]

    sky_pos = SkyCoord(ras, decs, unit=(u.deg, u.deg))

    # The use of circmean is accurate only when delta(dec) is small. For the
    # GPM declination strips this is the case.
    mean_ra = circmean(sky_pos.ra)
    mean_dec = np.mean(sky_pos.dec)

    if refine_position:
        logger.debug("Refining the mean position with a ZEA WCS type projection")
        logger.debug(f"{mean_ra} {type(mean_ra)}")
        logger.debug(f"{mean_dec} {type(mean_dec)}")

        mean_ra, mean_dec = zea_centre(ras, decs, (mean_ra.to(u.deg).value, mean_dec.to(u.deg).value))

    mean_pos = SkyCoord(mean_ra, mean_dec, unit=(u.deg, u.deg))

    if print_pos:
        print(f"{mean_pos.ra.deg} {mean_pos.dec.deg}")

    return mean_ra, mean_dec


if __name__ == "__main__":

    parser = ArgumentParser(
        description="Given a set of FITS files, extract their RA/Dec center and then calculate the mean position from this set"
    )

    parser.add_argument(
        "files",
        nargs="+",
        type=str,
        help="Path to the (many) FITS files to extract the position from ",
    )

    parser.add_argument(
        "--filter-obsids",
        type=str,
        default=None,
        help="Provided a GPM obsid text file (new line delimited), filter out files that do not contain a desired obsid. ",
    )

    parser.add_argument(
        "--verbose",
        default=False,
        action="store_true",
        help="Enable extra output when running",
    )

    parser.add_argument(
        "--ra-field",
        default="CRVAL1",
        type=str,
        help="Field name that contains the RA value",
    )
    parser.add_argument(
        "--dec-field",
        default="CRVAL2",
        type=str,
        help="Field name that contains the Dec value",
    )
    parser.add_argument(
        '--refine-position',
        default=False,
        action='store_true',
        help="Project images onto a mock ZEA projection to further refine the final central position"
    )

    args = parser.parse_args()

    if args.verbose is True:
        logger.setLevel(logging.DEBUG)

    calculate_mean(
        args.files,
        print_pos=True,
        filter_obsids=args.filter_obsids,
        ra_field=args.ra_field,
        dec_field=args.dec_field,
        refine_position=args.refine_position
    )
