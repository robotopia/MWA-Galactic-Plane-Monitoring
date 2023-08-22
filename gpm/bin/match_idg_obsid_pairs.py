#!/usr/bin/env python
import os 
import logging
from glob import glob
from argparse import ArgumentParser
from typing import Collection, Dict

import numpy as np
import pandas as pd
import astropy.units as u
from astropy.io import fits 
from astropy.coordinates import SkyCoord, EarthLocation, match_coordinates_sky
from astropy.time import Time
from astropy.table import Table 

logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(lineno)d:%(levelname)s %(message)s")
logger.setLevel(logging.INFO)

MWA = EarthLocation.from_geodetic(
    lat=-26.703319 * u.deg, lon=116.67081 * u.deg, height=377 * u.m
)
DEC_POINTINGS = [-71, -55, -41, -39, -26, -12, 3, 20]

def process_df(df: pd.DataFrame) -> pd.DataFrame:
    """Apply some preprocessing to the observations, including the calculation of
    standardised declination strips and hour-angle assignment. 

    Args:
        df (pd.DataFrame): Input dataframe of a gpm style observation table

    Returns:
        pd.DataFrame: Preprocessed observation table
    """
    # Unwrap the LST which is going above 360 degrees
    df['lst_deg_wrap'] = df['lst_deg'] % 360
    
    # Dec strip
    dec = np.array([-71.0, -55.0, -41.0, -39.0, -26.0, -12.0, 3.0, 20.0])
    logger.debug(f"Matching to nearest dec strip: {dec}")
    min_dec = lambda x: dec[np.argmin(np.abs(dec - x["dec_pointing"]))]
    df["dec_strip"] = df.apply(min_dec, axis=1)

    # Hour angle
    gps = Time(df["obs_id"], format="gps", location=MWA)
    lst = gps.sidereal_time("mean")

    ra = df["ra_pointing"].values
    ha = np.round((lst.deg - ra) / 15)

    mask = ha > 12
    ha[mask] = ha[mask] - 24.0

    mask = ha < -12
    ha[mask] = ha[mask] + 24.0

    df['ha'] = ha.astype(int)
    df = df[df['ha'].isin((-1,0,1))]

    # target = SkyCoord(
    #     '05:23:34 -69:45:22',
    #     unit=(u.hourangle, u.degree)
    # )
    # pos = SkyCoord(df.ra_pointing*u.deg, df.dec_pointing*u.deg)
    # match = target.separation(pos) < (15*u.deg)
    # logger.info(f"Number of matches {np.sum(match)}")

    # df = df.loc[match]

    return df


def load_gx_observations(gpm_db: str, filter_obsids: Collection[int]=None) -> pd.DataFrame:
    """Load in the GPM observation table

    Args:
        gpm_db (str): Address of the gpm pipeline database
        filter_obsids (Collection[int], optional): Only include observation if the obsid is in this set. Defaults to None.

    Returns:
        pd.DataFrame: Table of GPM observations and properties
    """
    logger.info(f"Polling {gpm_db}")
    
    df = pd.read_sql(
        'select * from observation',
        f'mysql://gpmdb@{gpm_db}/gpm'
    )
    
    logger.info(f"GPM observations loaded: {len(df)} observations")

    if filter_obsids is not None:
        logger.info('Filtering the GPM observation table')
        filt_mask = df['obs_id'].isin(filter_obsids)
        df = df[filt_mask]

        logger.info(f"{len(df)} rows remaing")

    df = process_df(df)

    return df 

def load_gpm_db(gpm_db: str, filter_obsids: Collection[int]=None) -> pd.DataFrame:
    """Load in the GPM observation table

    Args:
        gpm_db (str): Address of the gpm pipeline database
        filter_obsids (Collection[int], optional): Only include observation if the obsid is in this set. Defaults to None.

    Returns:
        pd.DataFrame: Table of GPM observations and properties
    """
    logger.info(f"Polling {gpm_db}")
    df = pd.read_sql(
        'select * from observation',
        f'mysql://gpmdb@{gpm_db}/gpm'
    )
    
    logger.info(f"GPM observations loaded: {len(df)} observations")
    
    if filter_obsids is not None:
        logger.info('Filtering the GPM observation table')
        filt_mask = df['obs_id'].isin(filter_obsids)
        df = df[filt_mask]

        logger.info(f"{len(df)} rows remaing")


    df = process_df(df)
   
    return df


def read_obsids(gpm_obsids: str) -> Collection[int]:
    """Read in a new-line delimited set of obsids from a text file. 

    Args:
        gpm_obsids (str): Path to text file to process

    Returns:
        Collection[int]: Collection of obsids loaded from obsids file
    """
    if not os.path.exists:
        logger.debug(f"{gpm_obsids} path does not exist. ")
        return None

    logger.info(f"Loading {gpm_obsids} file.") 
    obsids = np.loadtxt(gpm_obsids, dtype=int)

    logger.info(f"Loaded {len(obsids)} obsids")

    return obsids 


def associate_metafits_to_gx(
    out: str= None, 
    gpm_db: str='146.118.68.233', 
    gpm_obsids: str=None, 
    gpm_obsids: str=None
    ):
    """Search for nearest GPM obsid for each GPM metafits file, ensuring matching
    central channels. Also provide three sets of results corresponding to each of the 
    three GPM hour-angles

    Args:
        out (str, optional): Base file name to create output fits and txt files. If None, no output files are created. Defaults to None.
        gpm_db (str, optional): Address to the gpm database. Defaults to 146.118.68.233.
        gpm_obsids (str, optional): Path to a new-line delimited file of gpm obsids to filter to. Defaults to None. 
        gpm_obsids (str, optional): Path to a new-line delimited file of gpm obsids to filter to. Defaults to None. 
    """
    g_df = load_gpm_db(
        gpm_db=gpm_db,
        filter_obsids=read_obsids(gpm_obsids) if gpm_obsids is not None else None  
    )

    gx_df = load_gx_observations(
        gpm_db=gpm_db, 
        filter_obsids=read_obsids(gpm_obsids) if gpm_obsids is not None else None
    )

    results = []
    for (cenchan, delays), gx_sub_df in gx_df.groupby(['cenchan', 'delays']):
        logger.info(f"GPM subset: {cenchan=} {delays=}")
        g_sub_df = g_df[
            (g_df['cenchan'] == cenchan) & 
            (g_df['delays'] == delays)
        ]

        logger.info(f"Sub GPM df: {len(gx_sub_df)} rows")
        logger.info(f"Sub GPM df: {len(g_sub_df)} rows")

        if len(gx_sub_df) == 0 or len(g_sub_df) == 0:
            logger.info("Empty catalogue. Next set. ")
            continue 

        gx_sub_sky = SkyCoord(
            gx_sub_df['ra_pointing']*u.deg,
            gx_sub_df['dec_pointing']*u.deg,
        )

        g_sub_sky = SkyCoord(
                    g_sub_df['ra_pointing']*u.deg,
                    g_sub_df['dec_pointing']*u.deg,
        )

        # Do the match
        match_res = match_coordinates_sky(
            gx_sub_sky,
            g_sub_sky,
            nthneighbor=1
        )

        gx_sub_df.columns = [f"{c}_gpm" for c in gx_sub_df]
        g_sub_df.columns = [f"{c}_gpm" for c in g_sub_df]

        join_df = pd.concat(
            [
                gx_sub_df.reset_index(drop=True),
                g_sub_df.iloc[match_res[0]].reset_index(drop=True)
            ],
            axis=1
        )
        join_df['sep_arcmin'] = match_res[1].to(u.arcmin).value

        results.append(join_df)
 
    else:
        if len(results) == 0:
            logger.info("No results to output.")
            return

    results_df = pd.concat(results).reset_index()
    logger.debug(results_df.columns.tolist())
    logger.debug(results_df[[
            'obs_id_gpm','obs_id_gpm',
            'lst_deg_wrap_gpm','lst_deg_wrap_gpm',
            'ra_pointing_gpm','ra_pointing_gpm',
            'dec_pointing_gpm','dec_pointing_gpm', 
            'ha_gpm', 'ha_gpm',
            # 'delays_gpm', 'delays_gpm',
            'sep_arcmin']]
    )


    if out is not None:
        out_name = f"{out}_obsids.txt"
        logger.info(f"Writing slim list {out_name} with {len(results_df)} rows")
        logger.info(f"Number of unique GPM obsids: {len(results_df['obs_id_gpm'].unique())}")
        results_df.to_csv(
            out_name,
            sep=' ',
            columns=['obs_id_gpm','obs_id_gpm'],
            header=False,
            index=False,
        )
    
    return


if __name__ == '__main__':
    parser = ArgumentParser(description='Simple obsid matcher to associate GPM observation with the nearest GPM obsid')
    parser.add_argument('-o', '--out', type=str, default=None, help='Base path name to write to. Hour-angle and fits extension will be applied automatically. ')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='Increase level of output')
    parser.add_argument('-gpm-db', type=str, default='146.118.68.233', help='Address to mysql server hosting historic GPM observation data, in GPM style observation schema')
    parser.add_argument('--gpm-obsids', type=str, default=None, help='A new-line delimited collection of obsids to filter the gpm observations against. ')
    parser.add_argument('--gpm-obsids', type=str, default=None, help='A new-line delimited collection of obsids to filter the gpm observations against. ')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.debug(args)

    associate_metafits_to_gx(
        # args.metafits,
        out=args.out,
        gpm_db=args.gpm_db,
        gpm_obsids=args.gpm_obsids,
        gpm_obsids=args.gpm_obsids
    )
