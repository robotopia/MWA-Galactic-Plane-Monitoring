#!/usr/bin/env python

"""Script to help identify which calibrate solution files are not appropriate to apply, and helps to 
identify ones close in time that are appropriate. 
"""

import os
import numpy as np
from calplots.aocal import fromfile
from argparse import ArgumentParser

THRESHOLD = (
    0.25  # acceptable level of flagged solutions before the file is considered ratty
)


def check_solutions(aofile, threshold=THRESHOLD, segments=None, *args, **kwargs):
    """Inspects the ao-calibrate solutions file to evaluate its reliability

    Args:
        aofile (str): aocal solutions file to inspect
    
    Keyword Args:
        threshold (float): The threshold, between 0 to 1, where too many solutions are flagged before the file becomes invalid (default: 0.25)

    Returns:
        bool: a valid of invalid aosolutions file
    """
    threshold = threshold / 100 if threshold > 1 else threshold
    if not os.path.exists(aofile):
        return False

    ao_results = fromfile(aofile)
    ao_flagged = np.sum(np.isnan(ao_results)) / np.prod(ao_results.shape)

    if ao_flagged > threshold:
        return False

    if segments is not None: 
        segments = int(segments)

        assert ao_results.shape[0] == 1, "Segment checks not implemented across multiple time steps"
        
        # shape is timestep, antenna, channel, pol
        no_chan = ao_results.shape[2]
        
        assert no_chan % segments == 0, f"{no_chan} channels is not evenly divisible by {segments} segments"
        stride = no_chan // segments
        
        for i in range(segments):
            chan_slice = slice(i*stride, (i+1)*stride)
            seg_ao_data = ao_results[:,:,chan_slice,:]
            seg_ao_flagged = np.sum(np.isnan(seg_ao_data)) / np.prod(seg_ao_data.shape)

            if seg_ao_flagged > threshold:
                return False
        
    return True


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Detects whether a calibration solution was successfully derived. "
        )
    parser.add_argument(
        "-t",
        "--threshold",
        default=THRESHOLD,
        type=float,
        help=f"Threshold (between 0 to 1) of the acceptable number of NaN solutions before the entirety of solutions file considered void, defaults to {THRESHOLD}",
    )

    parser.add_argument(
        '-s',
        '--segments',
        type=int,
        default=None,
        help='Consider the flagging statistic checks on N number of sub-band segments. '
    )

    parser.add_argument(
        "aofile",
        type=str,
        nargs="+",
        help="Path to ao-solution file/s to check to see if it is valid",
    )

    args = parser.parse_args()

    print("Checking Mode")
    if args.segments is not None:
        print(f"Applying threshold checks to {args.segments} sub-bands")
    
    for f in args.aofile:
        if check_solutions(f, threshold=args.threshold, segments=args.segments):
            print(f"{f} passed")
        else:
            print(f"{f} failed")
