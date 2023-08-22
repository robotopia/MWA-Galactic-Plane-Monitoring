#! /usr/bin/env python

import sys
import numpy as np
import logging, warnings
import matplotlib.pyplot as plt
from astropy.io import fits
from argparse import ArgumentParser
from typing import Iterable, Tuple
from astropy.wcs import WCS
from astropy.nddata import Cutout2D
from astropy.nddata.utils import NoOverlapError
from astropy.utils.exceptions import AstropyWarning
from tqdm import tqdm

warnings.simplefilter("ignore", category=AstropyWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

PLOT = False  # Was only used throughout debugging.


def weighted_mean(maps: np.ndarray, weights: np.ndarray = None):
    """Perform the means through and array of shape (N,X,Y)

    Args:
        maps (np.ndarray): Input maps to average
        weights (bool, optional): Weight the mean by the inverse variance. Defaults to None.
    """
    logger.debug(f"weight_mean maps shape is {maps.shape}")
    logger.info(f"Calculating weighted average...")

    if weights is None:
        logger.info("No weights specific, assuming equal weights. ")
    else:
        weights = np.ma.masked_array(weights, np.isnan(weights))

    masked_maps = np.ma.masked_array(maps, np.isnan(maps))

    data = np.ma.average(masked_maps, axis=0, weights=weights).filled(np.nan)

    logger.debug(f"weight_mean averaged shape is {data.shape}")

    return data


def calculate_weights(
    psfs: Iterable[str],
    rmss: Iterable[str],
    nan_fill: float = np.nan,
    progress: bool = False,
    box_size: Tuple[int, int] = (50, 50),
):
    """Calculate the weights for the provided RMS files

    Args:
        psfs (Iterable[str]): Path to PSF fit cubes
        rmss (Iterable[sre]): Path to the coadded RMS files
    
    Keyword Args:
        nan_fill (float): Value to use when NaNs are found for the RMS std
        box_size (tuple[int, int]): Box size in pixels to use when calculating the average RMS (Defaults: (50, 50))
    """
    weight_cube = []
    for psf, rms in zip(psfs, rmss):
        logger.info(f"Calculating average RMS across {psf}")
        logger.info(f"Box size for each sampling is {box_size}")
        with fits.open(psf) as psf_fits, fits.open(rms) as rms_fits:

            # psf fits images have (bmaj, bmin, bpa, blur) images. The first will do.
            idxs = np.indices(psf_fits[0].data[0].shape).reshape((2, -1))
            psf_wcs = WCS(psf_fits[0].header).celestial
            psf_sky = psf_wcs.pixel_to_world(idxs[1], idxs[0])

            rms_wcs = WCS(rms_fits[0].header)

            logger.debug(f"Shape of psf_fits {psf}: {psf_fits[0].data.shape}")
            logger.debug(f"Shape for rms_fits is {rms_fits[0].data.shape}")

            rms_img = np.zeros_like(idxs[0], dtype=np.float32)
            valid = 0
            for idx, pos_sky in tqdm(enumerate(psf_sky), disable=not progress):
                try:
                    d = Cutout2D(
                        rms_fits[0].data,
                        pos_sky,
                        wcs=rms_wcs,
                        size=box_size,
                        fill_value=np.nan,
                        mode="partial",
                    )
                    if np.all(np.isnan(d.data)):
                        pos_rms = nan_fill
                    else:
                        pos_rms = np.nanmean(d.data)
                        valid += 1
                except NoOverlapError:
                    pos_rms = nan_fill
                except ValueError:
                    pos_rms = nan_fill

                rms_img[idx] = pos_rms

            rms_img = rms_img.reshape(psf_fits[0].data[0].shape)
            weight_cube.append(rms_img)

            logger.debug(f"Value of rms_img for {psf} is {np.nansum(rms_img)}")
            logger.debug(f"...... max is {np.nanmax(rms_img)}")
            logger.debug(f"...... max is {np.nanmin(rms_img)}")
            logger.debug(f"Number of valid pixels {valid}")

            if PLOT:
                fig, ax = plt.subplots(1, 1)

                ax.imshow(rms_img)

                fig.savefig(f"{psf}.rms.png")

                fig, ax = plt.subplots(1, 1)

                ax.imshow(psf_fits[0].data[0])

                fig.savefig(f"{psf}.slice0.png")

    logger.info("Inverting collected average RMS into weights")
    return 1.0 / np.array(weight_cube) ** 2


def combine_psf_cubes(
    psfs: Iterable[str],
    rmss: Iterable[str] = None,
    output: str = None,
    progress: bool = False,
    box_size: Tuple[int, int] = (50, 50),
):
    """Combine the psf cubes.

    Args:
        psfs (Iterable[str]): Paths to the psf cubes to process
    
    Keywords Args:
        rmss (Iterable[str]): Paths to the rms files that are used to weight each cube (Defaults: None)
        output (str): If not NOne, sets the path to save the averaged PSF parameters to. The header of the first 'psfs' will be used. (Default: None)
        progress (bool): Display a progress bar when calculating the weights (Default: False)
        box_size (tuple[int, int]): Box size in pixels to use when calculating the average RMS (Defaults: (50, 50))
    """
    weights = None
    if rmss is not None:
        assert len(psfs) == len(
            rmss
        ), f"The number of psfs ({len(psfs)}) and rms ({len(rmss)}) maps do not match."

        # Output shape will be (nfiles, decpixs, rapixs)
        weights = calculate_weights(psfs, rmss, progress=progress, box_size=box_size)
        logger.debug(f"Computed weight shape is {weights.shape}")

    psf_fits = [fits.open(p) for p in psfs]

    # shape is (nfiles, beamsparams, decpixs, rapixs)
    # switch the nfiles and beams around
    psf_data = np.array([psf[0].data for psf in psf_fits])
    psf_data = psf_data.swapaxes(0, 1)
    logger.debug(f"PSF data cube shape is {psf_data.shape}")

    # Iterating over beamparams means same shape as weights computed above
    psf_cube = np.array([weighted_mean(i, weights=weights) for i in psf_data])
    logger.debug(f"Average pdf data cube is {psf_cube.shape}")

    if output is not None:
        logger.info(f"Creating output file {output}")
        fits.writeto(
            output, data=psf_cube, header=psf_fits[0][0].header, overwrite=True
        )

    if PLOT:
        fig, axes = plt.subplots(2, 2)

        for ax, img in zip(axes.flatten(), psf_cube):
            ax.imshow(img)

        fig.tight_layout()
        fig.savefig("psf_cube.png")

        if weights is not None:
            sampling = np.sum(np.isfinite(weights), axis=0)

            fig, ax = plt.subplots(1, 1)

            cim = ax.imshow(sampling)
            ax.set(title="Valid Pixels across field")

            fig.colorbar(cim, label="Number of Valid Pixels")
            fig.tight_layout()
            fig.savefig("psf_sampling.png")


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Combine the project psf cubes created from many drift_mosaic scripts into a single cube"
    )

    parser.add_argument(
        "-p", "--psf", nargs="+", help="Path to psf projected cubes", default=None
    )
    parser.add_argument(
        "-r",
        "--rms",
        nargs="+",
        help="RMS maps that are used as the basic of an inverse variance weighting scheme",
        default=None,
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output path to place the computed aver PSF and blur factor files",
    )
    parser.add_argument(
        "--progress",
        default=False,
        action="store_true",
        help="Displace a progress bar can calculating the weights",
    )
    parser.add_argument(
        "-b",
        "--box-size",
        nargs=2,
        default=(50, 50),
        type=int,
        help="Box size, in pixels, to use for each measure of the RMS around a point in the PSF map",
    )

    args = parser.parse_args()

    if args.psf is None:
        parser.print_help()
        sys.exit(1)

    if args.rms is not None:
        assert len(args.psf) == len(
            args.psf
        ), "The lengths of the supplied psf and rms files is not the same. "

    combine_psf_cubes(
        args.psf,
        rmss=args.rms,
        output=args.output,
        progress=args.progress,
        box_size=args.box_size,
    )

