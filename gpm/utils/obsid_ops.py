#!/usr/bin/env python

"""Manage basic obsid operations from a set of obsids
"""

import os
import numpy as np
import pandas as pd
import astropy.units as u
from glob import glob
from argparse import ArgumentParser
from astropy.coordinates import SkyCoord
from astropy.stats.circstats import circmean

try:
    from gpm.db import mysql_db as gxdb
except:
    gxdb = None

CHECK_MODES = ["gpu", "vis", "folder"]
GALACTIC_PLANE_LIMITS = [-10, 10, 90, 270]


def clean_obsids(obsids):
    """Ensure a consistency to the provided set of obsids in terms of datatypes and format

    Args:
        obsids (Iterable): Obsids to process
    """
    obsids = [int(obsid) for obsid in obsids]

    return obsids


def read_obsids_file(path):
    """Simple file reader for a line delimited obsid set, typical within the GPM pipeline

    Args:
        path (str): File path to a list of obsids
    
    Returns:
        list[int]: List of ints that describe the GPM observation IDs
    """
    obsids = np.loadtxt(path)
    obsids = clean_obsids(obsids)

    return obsids


def write_obsids_file(obsids, path, clobber=True, *args, **kwargs):
    """Write a new-line delimited file of obsids

    Args:
        obsids (Iterable): Obsids to write out
        path (str): Path to write obsids to

    Keyword Args:
        clobber (bool): Overwrite existing file if it exists
    """
    obsids = clean_obsids(obsids)

    if not clobber and os.path.exists(path):
        raise FileExistsError(f"Output file {path} already exists")

    with open(path, "w") as outfile:
        print(f"Writing {path} with {len(obsids)} obsids")
        for obsid in obsids:
            print(obsid, file=outfile)


def obsids_from_db(obsids):
    """Obtain the observation details from the gpm database

    Args:
        obsids (Iterable): List of observations ids to obtain
    
    Returns:
        pandas.DataFrame: Constructed properties based on GPM observations table
    """
    if gxdb is None:
        raise ValueError("GPM database module not available")

    dbconn = gxdb.connect()

    cursor = dbconn.cursor()
    cursor.execute(
        f"SELECT * FROM observation WHERE obs_id IN ({', '.join(['%s' for _ in obsids])})",
        (*obsids,),
    )

    columns = [c[0] for c in cursor.description]
    df = pd.DataFrame(cursor.fetchall(), columns=columns)

    return df


def split(path, column="cenchan", *args, **kwargs):
    """Spilt obsids up based on some characteristic from a column of the constructed dataframe

    Properties are constructed / extracted from the GPM meta-data database

    Args:
        path (str): Path to line-delimited obsid file 
    
    Keyword Args:
        column (str): Column name of the constructed dataframe. 
    """
    obsids = read_obsids_file(path)
    obsids_df = obsids_from_db(obsids)

    for idx, sub_df in obsids_df.groupby(by=column):
        sub_obsids = clean_obsids(sub_df["obs_id"])

        name, ext = os.path.splitext(path)
        out_path = f"{name}_{column}_{int(idx):03d}{ext}"

        write_obsids_file(sub_obsids, out_path, *args, **kwargs)


def check(path, check_type):
    """Loads a GPM obsid file and checks for whether there is a corresponding file present in the working directory

    Args:
        path (str): Path to new-line delimited obsids file
        check_type (str): Type of files to search for
    
    Returns:
        list[int]: Collection of obsids that are missing
    """
    if check_type not in CHECK_MODES:
        raise ValueError(f"Available modes are {CHECK_MODES}, received {check_type}")

    if check_type == "gpu":
        candidates = [f.split("_")[0] for f in glob("vis.zip")]
    elif check_type == "vis":
        candidates = [f.split("_")[0] for f in glob("*ms.zip")]
    else:
        candidates = glob("[0-9]" * 10)

    obsids = set(read_obsids_file(path))
    candidates = set(clean_obsids(candidates))

    missing = list(obsids - candidates)

    return missing


def append(paths):
    """Append a list of files with obsids together

    Args:
        paths (iterable[str]): Iterable of file names to append
    """
    obsids = [obsid for f in paths for obsid in read_obsids_file(f)]

    return obsids


def mask_gp(path):
    """Mask out obsids in the region near the galactic plane

    Args:
        path (str): Path to new-line delimited obsid file
    """
    obsids = read_obsids_file(path)

    df = obsids_from_db(obsids)
    sky = SkyCoord(df["ra_pointing"], df["dec_pointing"], unit=(u.deg, u.deg))

    l = sky.galactic.l.deg
    b = sky.galactic.b.deg

    mask = (
        (b >= GALACTIC_PLANE_LIMITS[0])
        & (b <= GALACTIC_PLANE_LIMITS[1])
        & ((l <= GALACTIC_PLANE_LIMITS[2]) | (l >= GALACTIC_PLANE_LIMITS[3]))
    )

    df = df[~mask]

    obsids = clean_obsids(df["obs_id"])

    return obsids


def ra_ranges(path, min_ra=0, max_ra=360, ra_groups=1, write_output=False, auto=False):
    """Divide obdsids up based on RA group specifications

    Args:
        path (str): Path to new-line delimited obsid file
    """
    obsids = read_obsids_file(path)

    df = obsids_from_db(obsids)

    if auto:
        # Padding the limits to ensure all obsids as selected below
        min_ra = min(df["ra_pointing"]) - 1
        max_ra = max(df["ra_pointing"]) + 1

    boundaries = np.linspace(min_ra, max_ra, num=ra_groups + 1, endpoint=True)

    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        obsids = clean_obsids(
            df["obs_id"][(lower <= df["ra_pointing"]) & (df["ra_pointing"] < upper)]
        )

        if write_output:
            outname = path.split(".")
            outname = (
                f"{'.'.join(outname[:-1])}_ra_{lower:.0f}-{upper:.0f}.{outname[-1]}"
            )

            write_obsids_file(obsids, outname)


def mean_position(path, print_pos=False):
    """Calculate the mean position in a collection of obsids

    Args:
        path (str): path to text file with obsids, new line delimited
    
    Keyword Args:
        print_pos (bool): print the RA, Dec out to stdout (default is False)
    """
    obsids = read_obsids_file(path)

    df = obsids_from_db(obsids)

    positions = SkyCoord(df["ra_pointing"], df["dec_pointing"], unit=(u.deg, u.deg))
    # The use of circmean is accurate only when delta(dec) is small. For the
    # GPM declination strips this is the case.
    mean_ra = circmean(positions.ra)
    mean_dec = positions.dec.mean()
    mean_pos = SkyCoord(mean_ra, mean_dec)

    if print_pos:
        print(f"{mean_pos.ra.deg} {mean_pos.dec.deg}")

    return mean_pos.ra.deg, mean_pos.dec.deg


if __name__ == "__main__":
    parser = ArgumentParser(description="Basic operations on sets of obsids")

    parser.add_argument(
        "obsids", type=str, help="Path to new-line delimited set of obsids"
    )

    subparsers = parser.add_subparsers(dest="mode")

    split_parser = subparsers.add_parser(
        "split", help="Split a set of obsids up based on their cenchan propert"
    )
    split_parser.add_argument(
        "-c",
        "--clobber",
        default=True,
        action="store_false",
        help="Overwrite existing output file if it already exists",
    )

    check_parser = subparsers.add_parser(
        "check_files",
        help="Compares the obsids in the new-line delimited file against files / folders to see what is missing",
    )

    check_parser.add_argument(
        "type",
        default="gpu",
        choices=CHECK_MODES,
        help="Which type of file to search for (ms.zip or vis.zip)",
    )

    append_parser = subparsers.add_parser(
        "append",
        help="Append a set of new-line delimited obsid files to the end of the primary obsid file",
    )
    append_parser.add_argument(
        "obsids",
        nargs="+",
        help="Path to new-line delimited obsid files to concatenate together",
    )

    append_parser.add_argument(
        "-o", "--output", default=None, help="Output file to write obsids to"
    )

    mask_gp_parser = subparsers.add_parser(
        "mask_gp",
        help=f"Mask out obsids whose (l, b) are within [b_min, b_max, l_min, l_max], where limits are {GALACTIC_PLANE_LIMITS}. Masking assumes l=0 degrees is at the centre and increases left through right, wrapping at 180 degrees. ",
    )
    mask_gp_parser.add_argument(
        "-o", "--output", default=None, help="Output file to write obsids to"
    )

    rasplit_parser = subparsers.add_parser(
        "rasplit", help="Split the obsids into RA ranges"
    )
    rasplit_parser.add_argument(
        "--min-ra",
        default=0,
        type=float,
        help="The lower RA limit in degrees. Check is inclusive. ",
    )
    rasplit_parser.add_argument(
        "--max-ra",
        default=360,
        type=float,
        help="The maximum RA limit in degrees. Check is not inclusive. ",
    )
    rasplit_parser.add_argument(
        "--ra-groups", default=1, type=int, help="The number of RA segements to form"
    )
    rasplit_parser.add_argument(
        "--write-output",
        default=False,
        action="store_true",
        help="Create output files of the obsids grouped by RA (auto-generated names)",
    )
    rasplit_parser.add_argument(
        "--auto",
        default=False,
        action="store_true",
        help="Automatically selected RA limits based on those observed by the set of obsids. Ignored any provided min-ra of max-ra options. ",
    )

    meanpos_parser = subparsers.add_parser(
        "meanpos", help="Calculate the mean position from a set of positions"
    )

    args = parser.parse_args()

    if args.mode == "split":
        split(args.obsids, clobber=args.clobber)

    elif args.mode == "check_files":
        missing = check(args.obsids, args.type)

        missing = list(set(missing))
        for obsid in missing:
            print(obsid)

    elif args.mode == "append":
        obsids = append(args.obsids)
        if args.output is not None:
            write_obsids_file(obsids, args.output)

    elif args.mode == "mask_gp":
        obsids = mask_gp(args.obsids)
        if args.output is not None:
            write_obsids_file(obsids, args.output)

    elif args.mode == "rasplit":
        ra_ranges(
            args.obsids,
            min_ra=args.min_ra,
            max_ra=args.max_ra,
            ra_groups=args.ra_groups,
            write_output=args.write_output,
            auto=args.auto,
        )
    elif args.mode == "meanpos":
        mean_position(args.obsids, print_pos=True)

    else:
        print(f"Directive mode {args.mode} not present. ")
