#!/usr/bin/env python

#################################################
#
# This script is modelled on:
#   https://github.com/CsanadHorvath/Transients/blob/main/run_on_pawsey.py
#
# The bit that does the actual work is the call to TransientSearch(),
# and the main differences between this script and the run_on_pawsey.py
# script are just how the set-up is done to call that function from the
# GPM pipeline itself.
#
###################################################

from transient_search import *
import filters as fil
from astropy.io import fits
import argparse
import os

filters = [
    Filter('tcg'  , 5.5, 7.0, True , fil.Correlator, (1,1,1), (125,1,1)),
    Filter('spike', 5.5, 7.5, False, fil.Spike, 3),
    Filter('rms'  , 2.0, 2.25, True , fil.RMS)
]


def main():
    # Parse the command line arguments
    parser = argparse.ArgumentParser(description="Calls the tfilter code (https://github.com/CsanadHorvath/Transients)")

    parser.add_argument('transient_cube', help="The *absolute* path to the data cube containing the time-step images to be analysed")
    parser.add_argument('obsid', type=int, help="The ObsID of the observation")
    parser.add_argument('--run_name', default="gpm2024", help="The file stem name to use for various intermediate output files. Can be arbitrary, but safer to let this code use the default value.")
    parser.add_argument('--make_plots', type=bool, default=True, help="Save plots to disk? (default = True)")
    parser.add_argument('--save_filtered', type=bool, default=False, help="Save filter images? (default = False)")
    parser.add_argument('--max_plots', type=int, default=150, help="Only make a maximum of this many plots (default = 150)")
    parser.add_argument('--true_mask', type=bool, help="Not 100% sure what this does, but something to do with matching to the sky catalogue. Probably mainly useful for debugging. Only use this option if you know what you're doing!")
    parser.add_argument('--project', default="gpm2024", help="The project name to assign to the candidates being uploaded. For this pipeline, this should be 'gpm2024' (default = 'gpm2024')")

    args = parser.parse_args()

    # Use the same path as where the transient cube lived to also use as
    # the working directory for where to put all the outputs
    path = os.path.dirname(args.transient_cube) + '/{0}_{1}'

    cands = TransientSearch(
        path,
        args.obsid,
        filters,
        args.run_name,
        args.make_plots,
        args.save_filtered,
        args.project,
        max_plots=args.max_plots,
        true_mask=args.true_mask)

if __name__ == '__main__':
    main()
