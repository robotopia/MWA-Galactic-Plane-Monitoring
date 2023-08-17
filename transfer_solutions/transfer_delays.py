#!/usr/bin/env python
import os, logging
import argparse
from calplots.aocal import fromfile
import numpy as np
from pyrap import tables
import matplotlib.pyplot as plt

def main():

    parser = argparse.ArgumentParser(
        description="Adjust the phases of one calibration solution to best match those in another",
    )

    parser.add_argument('soln1', help="The calibration solution (.bin) whose phases are to be adjusted")
    parser.add_argument('soln2', help="The calibration solution (.bin) acting as a rough model")
    parser.add_argument('soln_out', help="Where to write the adjusted solutions")

    args = parser.parse_args()

    ao1 = fromfile(args.soln1)
    ao2 = fromfile(args.soln2)

    # Example shape:
    # (1, 136, 768, 4) = (timesteps??, tiles, frequencies, polarisations)

    # Ignore amplitude information -- we will transfer amps from ao1 directly
    ao1_phasor = ao1/np.abs(ao1)
    ao2_phasor = ao2/np.abs(ao2)

    # Get the average phase difference between them
    diff_phasor = ao2_phasor/ao1_phasor

    # Average the diff phasors over frequency
    avg_diff_phasor = np.nanmean(diff_phasor, axis=2)
    avg_diff_phasor /= np.abs(avg_diff_phasor)

    # ^^^ This assumes that the change in delay has not been big enough to make an
    # appreciable difference in the phase slope (i.e. compared to the noise and
    # other artefacts). In cases where the slope does change significantly (e.g.
    # picket fence observations over a much longer lever arm of frequency), you'd
    # have to fit a slope to the phase differences.

    # Apply this extra (average) phase difference to ao1
    ao1 *= avg_diff_phasor[:,:,np.newaxis,:]

    # Write out to file
    ao1.tofile(args.soln_out)

if __name__ == '__main__':
    main()
