#!/usr/bin/env python

from argparse import ArgumentParser

import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from astropy.wcs import WCS

__desc__ = """A small utility script to extract the PSF our of two projpsf_psf files. The idea being to select a position near the middle that both maps have coverage of. This middle point region is a very crude approximation. """


def extract_psf_beams(low_psf, high_psf, plot=False):
    """Find a common position in the (rough) center of both projected PSF maps, and output the beams to output

    Args:
        low_psf (str): Path to the lower frequency projected PSF map
        high_psf (str): Path to the higher frequency projected PSF map
        plot (bool, optional): If true, will create a simple diagnostic plot of the extracted region. Defaults to False.
    """
    with fits.open(high_psf) as high_psf, fits.open(low_psf) as low_psf:
        high_maj = high_psf[0].data[0]
        low_maj = low_psf[0].data[0]
        high_min = high_psf[0].data[1]
        low_min = low_psf[0].data[1]

        # This only works because the projpsf_psf files share the same WCS by design
        ratio_maj = high_maj / low_maj
        positions = np.argwhere(np.isfinite(ratio_maj))
        mid_pos = positions[positions.shape[0] // 2, :]

        # Althought this seemingly works find, not guaranteed to be a valid pixel
        #   mid_pos = np.mean(positions, axis=0).astype(int)

        print(f"Extracted mis position: {mid_pos}")
        print(
            f"Low nu beam: {low_maj[mid_pos[0], mid_pos[1]]*3600} {low_min[mid_pos[0], mid_pos[1]]*3600}"
        )
        print(
            f"High nu beam: {high_maj[mid_pos[0], mid_pos[1]]*3600} {high_min[mid_pos[0], mid_pos[1]]*3600}"
        )

        if plot:
            w = WCS(high_psf[0].header).celestial

            fig, ax = plt.subplots(1, 1, subplot_kw=dict(projection=w))

            ax.imshow(ratio_maj)
            ax.plot(mid_pos[1], mid_pos[0], "ro", label="Selected position")
            ax.legend()
            ax.set(
                title="Major axis ratio",
                xlabel="Right Ascension (J2000)",
                ylabel="Declination (J2000",
            )

            fig.savefig("wideband_psf_extraction.pdf")


if __name__ == "__main__":
    parser = ArgumentParser(description=__desc__)
    parser.add_argument("low_psf", help="Path to the low frequency projpsf_psf map")
    parser.add_argument("high_psf", help="Path to the high frequency projpsf_psf map")
    parser.add_argument(
        "-p",
        "--plot",
        default=False,
        action="store_true",
        help="Create a small diagnostic plot to visualise where the point was selected",
    )

    args = parser.parse_args()

    extract_psf_beams(args.low_psf, args.high_psf, plot=args.plot)

