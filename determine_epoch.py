#!/usr/bin/env python

# Determine the epoch number for our Galactic Monitoring campaign

from astropy.time import Time
import argparse

def epoch(obsid=None):
# Epoch numberering starts 1st May 2022
    epoch0 = Time("2022-05-01T00:00:00", format="isot", scale="utc")
    if obsid is None:
        now = Time.now()
        diff = now - epoch0
    else:
        now = Time(obsid, format="gps")
        diff = now - epoch0
# Y2k is 2032
    return(f"{int(diff.value):04d}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--obsid", dest='obsid', type=str, default=None,
                        help="An obsid to determine the epoch of. If not specified, determines epoch of now.")
    args = parser.parse_args()
    print(epoch(args.obsid))
