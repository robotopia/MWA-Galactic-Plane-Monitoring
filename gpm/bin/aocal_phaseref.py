#!/usr/bin/env python
from __future__ import print_function

import os, logging
from optparse import OptionParser
from calplots.aocal import fromfile
import numpy as np
from pyrap import tables

parser = OptionParser(
    usage="usage: %prog inbinfile outbinfile refant"
    + """
Divide through by phase of a single reference antenna
"""
)
parser.add_option(
    "-v",
    "--verbose",
    action="count",
    default=0,
    dest="verbose",
    help="-v info, -vv debug",
)
parser.add_option(
    "--incremental",
    action="store_true",
    dest="incremental",
    help="incremental solution",
)
parser.add_option(
    "--preserve_xterms",
    action="store_true",
    dest="preserve_xterms",
    help="preserve cross-terms (default is to set them all to 0+0j)",
)
parser.add_option(
    "--xy",
    default=0.0,
    dest="xy",
    type=float,
    help="add this phase (in degrees) to the YY phases for all channels",
)
parser.add_option(
    "--dxy",
    default=0.0,
    dest="dxy",
    type=float,
    help="add this slope (in degrees per hertz) in xy_phase to all YY phases ",
)
parser.add_option(
    "--ms",
    type=str,
    default=None,
    help="The measurement set the corresponds to the solutions file",
)
parser.add_option(
    "--no_preserve_mask",
    action='store_true',
    default=False,
    help='If used this will not carry forward the set of flagged channels as stored in the original aocal input file, replicating old behavour.  This should only be used if you know what you are doing. '
)

opts, args = parser.parse_args()

if len(args) != 3:
    parser.error("incorrect number of arguments")
infilename = args[0]
outfilename = args[1]
refant = int(args[2])

if opts.verbose == 1:
    logging.basicConfig(level=logging.INFO)
elif opts.verbose > 1:
    logging.basicConfig(level=logging.DEBUG)
if (opts.xy != 0.0 or opts.dxy != 0.0) and opts.preserve_xterms:
    parser.error("XY phase cannot be set if preserving xterms")

ao = fromfile(infilename)

ref_phasor = (ao[0, refant, ...] / np.abs(ao[0, refant, ...]))[
    np.newaxis, np.newaxis, ...
]
if opts.incremental:
    logging.warn("incremental solution untested!")
    ao = ao / (ao * ref_phasor)
else:
    ao = ao / ref_phasor

if not opts.preserve_xterms:
    zshape = (1, ao.n_ant, ao.n_chan)
    ao[..., 1] = np.zeros(zshape, dtype=np.complex128)
    ao[..., 2] = np.zeros(zshape, dtype=np.complex128)
if opts.xy != 0.0 or opts.dxy != 0.0:
    assert opts.ms is not None, "A measurment set has not be specified"

    tab = tables.table(f"{opts.ms}/SPECTRAL_WINDOW")
    freqs = np.squeeze(np.array(tab.CHAN_FREQ))
    tab.close()

    print(
        f"Frequencies have been read in, spanning {np.min(freqs)/1e6} to {np.max(freqs)/1e6} MHz. "
    )

    assert (
        len(freqs) == ao.n_chan
    ), f"Number of frequency solutions in the calibration file does not match the number of channels in {opts.ms}"

    xy_phasor0 = np.complex(np.cos(np.radians(opts.xy)), np.sin(np.radians(opts.xy)))
    xy_phasor1 = np.zeros((1, 1, ao.n_chan), dtype=np.complex128)
    xy_phasor1.real += np.cos(np.radians(opts.dxy * freqs)).reshape(1, 1, ao.n_chan)
    xy_phasor1.imag += np.sin(np.radians(opts.dxy * freqs)).reshape(1, 1, ao.n_chan)
    ao[..., 3] = ao[..., 3] * xy_phasor0 * xy_phasor1


if not opts.no_preserve_mask:
    print("Carrying forward NaN mask")
    initial_ao = fromfile(infilename)
    ao[np.isnan(initial_ao)] = np.nan

ao.tofile(outfilename)
