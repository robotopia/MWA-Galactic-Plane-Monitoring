#!/usr/bin/env python

from __future__ import print_function

import pandas as pd
import numpy as np
import astropy.units as u
from argparse import ArgumentParser
from astropy.time import Time
from astropy.coordinates import SkyCoord, EarthLocation

from gpm.db import mysql_db as mdb

MWA = EarthLocation.from_geodetic(
    lat=-26.703319 * u.deg, lon=116.67081 * u.deg, height=377 * u.m
)
# DEC_POINTINGS = [-71, -55, -41, -39, -26, -12, 3, 20]
DEC_POINTINGS = [-71, -55, -40, -26, -12, 3, 20]
GALACTIC_PLANE_LIMITS = [-10, 10, 90, 270]


def get_observations(
    all_obs=False,
    only_calobs=False,
    start_obsid=None,
    finish_obsid=None,
    obs_date=None,
    dec_pointing=None,
    cen_chan=None,
    hour_angle=None,
    mask_gp=False,
):

    if all_obs is True and only_calobs is True:
        raise ValueError("Both all_obs and only_calobs can not be True.")

    df = pd.read_sql_table("observation", mdb.dbconn)

    # The default behaviour of this script is to only return the 
    # GPM science fields, not the MWA calibration scans. 
    if only_calobs:
        df = df[~df["obsname"].str.contains("FDS")]    
    elif not all_obs:
        df = df[df["obsname"].str.contains("FDS")]
  
    if mask_gp:
        sky = SkyCoord(df["ra_pointing"], df["dec_pointing"], unit=(u.deg, u.deg))

        l = sky.galactic.l.deg
        b = sky.galactic.b.deg

        mask = (
            (b >= GALACTIC_PLANE_LIMITS[0])
            & (b <= GALACTIC_PLANE_LIMITS[1])
            & ((l <= GALACTIC_PLANE_LIMITS[2]) | (l >= GALACTIC_PLANE_LIMITS[3]))
        )

        df = df[~mask]

    if start_obsid is not None:
        df = df[df["obs_id"] >= int(start_obsid)]

    if finish_obsid is not None:
        df = df[df["obs_id"] <= int(finish_obsid)]

    if obs_date is not None:
        gps = Time(df["obs_id"], format="gps", location=MWA)
        gps_date = gps.strftime("%Y-%m-%d")

        df = df[gps_date == obs_date]

    if dec_pointing is not None:
        dec = np.array([-71.0, -55.0, -41.0, -39.0, -26.0, -12.0, 3.0, 20.0])
        min_dec = lambda x: dec[np.argmin(np.abs(dec - x["dec_pointing"]))]
        df["Dec Strip"] = df.apply(min_dec, axis=1)

        df = df[df["Dec Strip"] == dec_pointing]

    if hour_angle is not None:
        gps = Time(df["obs_id"], format="gps", location=MWA)
        lst = gps.sidereal_time("mean")

        ra = df["ra_pointing"].values
        ha = np.round((lst.deg - ra) / 15)

        mask = ha > 12
        ha[mask] = ha[mask] - 24.0

        mask = ha < -12
        ha[mask] = ha[mask] + 24.0

        df = df[ha.astype(int) == hour_angle]

    if cen_chan is not None:
        df = df[df["cenchan"] == cen_chan]

    return df


def create_obsids_txt(df, out):
    df["obs_id"].to_csv(out, index=False, header=False)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Pulls down a list of `obs_ids` provide a set of specifications"
    )
    parser.add_argument(
        "-a",
        "--all-obs",
        default=False,
        action="store_true",
        help="Include calibration scans as well as the FDS observations",
    )
    parser.add_argument(
        '--only-calobs',
        default=False,
        action='store_true',
        help='Download only the calibration observations matching the criteria'
    )
    parser.add_argument(
        "-s",
        "--start-obsid",
        default=None,
        type=int,
        help="First `obs_id` in a range of obsids",
    )
    parser.add_argument(
        "-f",
        "--finish-obsid",
        default=None,
        type=int,
        help="Last `obs_id` in a range of obsids",
    )
    parser.add_argument(
        "-d",
        "--date",
        default=None,
        help="Obsids on this date are returned. Date is expected in YYY-MM-DD format",
    )
    parser.add_argument(
        "-e",
        "--dec",
        default=None,
        type=int,
        choices=DEC_POINTINGS,
        help="Obsids from this dec strip are returned. ",
    )
    parser.add_argument(
        "-o",
        "--out",
        default=None,
        help="Output path of a line delimited set of obsids. Only supports text output file and ignores file extension. ",
    )
    parser.add_argument(
        "-c",
        "--cen-chan",
        default=None,
        type=int,
        choices=[69, 93, 121, 145, 169],
        help="Obsids matching the specified cenchan are returned. ",
    )
    parser.add_argument(
        "-i",
        "--hour-angle",
        default=None,
        type=int,
        choices=[-1, 0, 1],
        help="Specifies the hour-angle of the obsids to be returned. ",
    )

    parser.add_argument(
        "-m",
        "--mask-gp",
        default=False,
        action="store_true",
        help=f"Mask out obsids whose (l, b) are within [b_min, b_max, l_min, l_max], where limits are {GALACTIC_PLANE_LIMITS}. Masking assumes l=0 degrees is at the centre and increases left through right, wrapping at 180 degrees. ",
    )

    args = parser.parse_args()

    print(args)

    if args.all_obs is True and args.only_calobs is True:
        raise ValueError("--all-obs and --only-calobs are mutually exclusive operations. ")

    df = get_observations(
        all_obs=args.all_obs,
        only_calobs=args.only_calobs,
        start_obsid=args.start_obsid,
        finish_obsid=args.finish_obsid,
        obs_date=args.date,
        cen_chan=args.cen_chan,
        hour_angle=args.hour_angle,
        mask_gp=args.mask_gp,
    )

    print(df.shape)

    if args.out is not None:
        create_obsids_txt(df, args.out)
