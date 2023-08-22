#!/usr/bin/env python

"""A simply script used to flag antenna in a measurement set to support the binocular imaging mode.
These data ultimately are aimed towards supporting the traveling ionospheric distrubance analysis.

The measurement set will be divided into one of four directions: north, south, east, west. 
Antennas that do not belong to some direction are flagged. 

This script does not do any type of iteration over the directions -- a user will specify 
a metafits file, a measurement set and a direction. 

The position listed in the ANTENNA table of the measurement set of interest will be used to derive
positions, using th known MWA position. 

Math is shamelessly inspired by: https://archive.psas.pdx.edu/CoordinateSystem/Latitude_to_LocalTangent.pdf
"""

__author__ = ["TJG", "NHW"]

import os
import sys
from argparse import ArgumentParser
import logging
from typing import Iterable, Tuple, Union
from pathlib import Path

import pandas as pd
import astropy.units as u
from astropy.io import fits
from astropy.table import Table
import numpy as np
from astropy.coordinates import EarthLocation
from casacore.tables import taql, table

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(lineno)d:%(levelname)s %(message)s")
logger.setLevel(logging.INFO)


DIRECTIONS = ("north", "south", "east", "west")
MWA = EarthLocation.from_geodetic(
    lat=-26.703319 * u.deg, lon=116.67081 * u.deg, height=377 * u.m
)


def parse_antenna_ms(ms: Union[str,Path]) -> pd.DataFrame:
    """Convert the ANTENNA table of the supplied measurement set into a pandas dataframe

    Args:
        ms (Union[str, Path]): Path to the measurement set of interest

    Returns:
        pd.DataFrame: ANTENNA table from the supplied emasurement set 
    """

    logger.info(f"Parsing the antenna table of {ms}")
    ant_ms = table(f"{ms}/ANTENNA", readonly=True, ack=False)

    ant_df = pd.DataFrame([a for a in ant_ms])
    logger.info(f"Loaded {len(ant_df)} antennas")

    return ant_df

def create_rotation_matrices(ref0: EarthLocation) -> Tuple[np.ndarray, np.ndarray]:
    """Create the two sets of rotation matrices to convert the geodetic XYZ coordinates
    to the local tangent plane, with the origin/reference being that at the EarthLocation

    Args:
        ref0 (EarthLocation): The position that becomes the origin of LTP

    Returns:
        Tuple[np.ndarray, np.ndarray]: The (East, North, Up) position at the reference position in units of meters
    """
    
    logger.debug(f"Obtaining rotations for {ref0.lon} {ref0.lat}")

    # Math is shamelessly 'inspired' by: https://archive.psas.pdx.edu/CoordinateSystem/Latitude_to_LocalTangent.pdf
    phi = ref0.lon.rad
    lam = ref0.lat.rad
    
    # Precompute the trig functions used for later
    sin_phi, cos_phi = np.sin(phi), np.cos(phi)
    sin_lam, cos_lam = np.sin(lam), np.cos(lam)
    
    rot1 = (
        ( -sin_phi, cos_phi, 0 ),
        (  cos_phi, sin_phi, 0 ),
        (0, 0, 1)
    )
    
    rot2 = (
        ( 1, 0, 0 ),
        ( 0, -sin_lam, cos_lam ),
        (0, cos_lam, sin_lam)
    )
    
    return np.array(rot1), np.array(rot2)

def derive_local_tangent_plane(
    geodetic_pos: Iterable[float], ref0: EarthLocation
) -> Tuple[float,float,float]:
    """Convert the geodetic positions (XYZ) in meters to East-North-Up (ENU)
    in meters at the supplied reference position. 

    Args:
        geodetic_pos (Iterable[float]): A position in the geodetic frame to convert to ENU
        ref0 (EarthLocation): Reference/origin position of the LTP to produce the ENU positions

    Returns:
        Tuple[float,float,float]: ENU positions 
    """
    # any other preprocessing goes here
    ant_xyz = np.array(geodetic_pos) * u.m

    logger.debug(f"Antennas XYZ: {ant_xyz=}")

    # get the geodetic position from the EarthLocation
    ref_xyz = u.Quantity(ref0.geocentric).to(u.m)

    # get the two rotations that depend on the reference/origin
    # of the local tangent plane
    rot1, rot2 = create_rotation_matrices(ref0)

    # and finally apply the rotations to the offset XYZ position
    ant_enu = rot2 @ rot1 @ (ant_xyz - ref_xyz).value
    
    return tuple(ant_enu)

def get_ant_subarray_flags(ant_table: pd.DataFrame, direction: str) -> Iterable[bool]:
    """Using the ENU positions to derive the appropriate flags to split
    the array into the desired quadrant sub-array. 

    Args:
        ant_table (pd.DataFrame): ANTENNA table from a measurement of interest
        direction (str): Direction of interest, in either 'north', 'south', 'east', 'west'

    Raises:
        ValueError: An invalid direction has been supplied

    Returns:
        Iterable[bool]: Whether an antenna will be flagged (True) or unflagged (False)
    """

    # From NHW, as described in the GPM survey paper
    # To select these antennas I used the following criteria:
    # ants_east: East > 700 (43 antennas)
    # ants_west: East < -120 (44 antennas)
    # ants_north: North > 720 (44 antennas)
    # ants_south: North < -70 (43 antennas)

    logger.info(f"Flagging for direction {direction}")

    if direction == "east":
        mask = ant_table["East"] <= 700
    elif direction == "west":
        mask = ant_table["East"] >= -120
    elif direction == "north":
        mask = ant_table["North"] <= 720
    elif direction == "south":
        mask = ant_table["North"] >= -70
    else:
        logger.error(f"Supplied direction {direction} is invalid. ")
        raise ValueError("Invalid direction supplied")

    logger.debug(f"{mask=}")
    logger.debug(f"{np.sum(mask)}")
    
    idx_to_flag = np.argwhere(np.array(mask)).squeeze()

    logger.info(f"{len(idx_to_flag)} antennas will be flagged")

    ant_names = ant_table['NAME'].str.lower()
    if 'rfipole' in ant_names:
        logger.info(f"Detected 'rfipole' in antenna table. Flagging. ")
        ant_table.index[ant_names=='rfipol'] = True

    assert len(
        idx_to_flag
    ), f"Fewer than 60 antennas are being flagged. Something likely wrong. "

    return mask 

def plot_layout(ant_table: pd.DataFrame, direction: str, path: Union[str,Path]=None) -> None:
    """Make a diagnostic figure that highlights the MWA tile layout in
    as obtained by the ENU derivation. Will highlight the flagged and unflagged regions. 

    Args:
        ant_table (pd.DataFrame): ANTENNA table from a measurement set of interest
        direction (str): direction of interest, used purely for title
        path (Union[str,Path], optional): Location to save the figure to. Discarded otherwise. Defaults to None.
    """

    fig, ax = plt.subplots(1,1)

    mask = ant_table['FLAGGED']

    ax.plot(
        ant_table['East'][mask] / 1000,
        ant_table['North'][mask] / 1000,
        'ro',
        label='Flagged',
        ms=3
    )

    ax.plot(
        ant_table['East'][~mask] / 1000,
        ant_table['North'][~mask] / 1000,
        'bs',
        label='Not Flagged',
        ms=3
    )

    ax.set(
        xlabel='Easting (km)',
        ylabel='Northing (km)',
        title=f'Direction {direction}'
    )

    ax.grid()

    ax.legend()
    
    if path is not None:
        fig.tight_layout()
        fig.savefig(path)
    
def apply_flagging_to_ms(ms: Union[str, Path], idx_to_flag: Iterable[int]) -> None:
    """Given a set of antenna IDs (based on the index position of a ANTENNA table),
    use taql to flag visibilities

    Args:
        ms (Union[str,Path]): Measurement set to apply flagging to
        idx_to_flag (Iterable[int]): Antennas to flag
    """

    
    logger.info(f"Flagging {ms}")
    logger.info(f"Antennas to flag: {idx_to_flag}")

    unflag1 = taql("CALC sum([select nfalse(FLAG) from $ms])")

    for idx in idx_to_flag:
        taql(f"UPDATE $ms set FLAG_ROW=T WHERE ANTENNA1=={idx} || ANTENNA2=={idx}")
        taql(f"UPDATE $ms set FLAG=T WHERE ANTENNA1=={idx} || ANTENNA2=={idx}")

    unflag2 = taql("CALC sum([select nfalse(FLAG) from $ms])")

    logger.info(f"Flagged {int(unflag1 - unflag2)} visibilities")
    logger.info(f"{int(unflag2)} visibilities remain unflagged")

def ms_flag_by_direction(
    ms: Union[str,Path], direction: str = "north", apply: bool = True, plot: bool=False, dump_table: bool=False
) -> None:
    """Flag an MWA measurment set of interest into a quadrant. Antennas will be 
    flagged using taql, and flagged antennas are identified by converting the 
    POSITION field (XYZ) into a East-North-Up (ENU) at the MWA location. 

    Args:
        ms (Union[str,Path]): Path to a measurement set of interest
        direction (str, optional): Direction of interest. Acceptable values are 'north', 'south', 'east', 'west'. Defaults to "north".
        apply (bool, optional): Apply the antenna flagging using taql. Defaults to True.
        plot (bool, optional): Create a plot of the MWA layout and which tiles are to be flagged. Defaults to False.
        dump_table (bool, optional): Save the processed ANTENNA table, with ENU positions, to a csv. File name is based on the measurment set name. Defaults to False.
    """
    ms = Path(ms)
    if not ms.exists():
        logger.error(f"{ms} does not exist. Exiting. ")
        sys.exit(2)

    if direction not in DIRECTIONS:
        logger.error(f"Direction {direction} is not valid.")
        raise ValueError(f"Direction {direction} not valid. Acceptable values are {DIRECTIONS}.")

    ant_table = parse_antenna_ms(ms)

    logger.info(f"Using reference position of {MWA.lon} {MWA.lat}")

    # do transformation from XYZ-> ENU
    res = ant_table['POSITION'].apply(
        derive_local_tangent_plane, 
        args=(MWA,),
    )

    # and save them to the table
    ant_table[['East', 'North', 'Height']] = pd.DataFrame(res.tolist(), index=ant_table.index)

    logger.debug(ant_table[['POSITION', 'East', 'North']])

    # apply quadrant splitting criteria
    flag_mask = get_ant_subarray_flags(ant_table, direction)
    ant_table['FLAGGED'] = flag_mask

    # data products are produced below
    if plot:
        ext = f"_{direction}.png"
        out_path = f"{Path(str(ms).replace('.ms', ext))}"
        logger.info(f"Creating {out_path}")
        plot_layout(
            ant_table,
            direction,
            path=out_path
        )

    if dump_table:
        ext = f"_{direction}_table.csv"
        out_path = f"{Path(str(ms).replace('.ms', ext))}"
        logger.info(f"Creating {out_path}")
        ant_table.to_csv(out_path)

    # and now apply the flags
    if apply:
        idx_to_flag = np.argwhere(
            np.array(ant_table['FLAGGED'])
        ).squeeze()
        apply_flagging_to_ms(ms, idx_to_flag)


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Flag all antenna that do not correspond to a desired direction. "
    )
    parser.add_argument("ms", type=str, help="Path to a measurement set to flag")
    
    parser.add_argument(
        "-d",
        "--direction",
        type=str,
        default="north",
        choices=DIRECTIONS,
        help="The direction of interest. Antennas that do not form this subarray are flagged. ",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Extra logging is enabled",
    )
    parser.add_argument(
        "-a",
        "--apply",
        default=False,
        action="store_true",
        help="Apply flags if True. If False, just print the antenna indicies to flag. Defaults to False. ",
    )
    parser.add_argument(
        '-p',
        '--products',
        default=False,
        action='store_true',
        help='Create data products, including a figure of the MWA layout in the LTP, and table for record keeping'
    )
    parser.add_argument(
        '--all',
        default=False,
        action='store_true',
        help='Run against all direction. If enable, apply is forced to be False. '
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if args.all:
        for d in DIRECTIONS:
                # Will never apply the flagging
                ms_flag_by_direction(
                    args.ms,
                    direction=d,
                    apply=False,
                    plot=args.products,
                    dump_table=args.products
                )

    else:
        ms_flag_by_direction(
            args.ms,
            direction=args.direction,
            apply=args.apply,
            plot=args.products,
            dump_table=args.products
        )
