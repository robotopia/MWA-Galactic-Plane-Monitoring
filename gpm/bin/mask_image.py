#!/usr/bin/env python

import logging
from argparse import ArgumentParser

import numpy as np 
from astropy.io import fits 


logger = logging.getLogger(__name__)
logging.basicConfig(format="%(module)s:%(levelname)s:%(lineno)d %(message)s")
logger.setLevel(logging.INFO)

def derive_apply_beam_cut(image, xx_beam, yy_beam, apply_mask=False, level=5.):
    logger.info(f"Creating the stokes I beam")
    with fits.open(xx_beam, memmap=True) as xx_fits, fits.open(yy_beam, memmap=True) as yy_fits:
        logger.debug('Assiging the xx fits beam data')
        xx_data = xx_fits[0].data
        logger.debug('Assiging the yy fits beam data')
        yy_data = yy_fits[0].data

        logger.debug('Forming the stokes i beam')
        i_data = (xx_data + yy_data) / 2

        logger.info('Writing stokes I beam')
        xx_fits[0].data = i_data 
        xx_fits.writeto(xx_beam.replace('XX','I'), overwrite=True)

    logger.debug(f"Stokes I beam formed, data shape is {i_data.shape}")

    logger.info(f"Flagging below level {level} percent")

    i_mask = i_data*100. < level 
    logger.info(f"Flagging {np.sum(i_mask)} of {np.prod(i_data.shape)} pixels")

    if apply_mask:
        logger.info(f"Applying the mask")
        with fits.open(image) as in_img:
            in_img[0].data[i_mask] = np.nan

            in_img.writeto(image.replace('.fits','_mask.fits'), overwrite=True)

    else:
        logger.info('Not applying mask')


if __name__ == '__main__':
    parser = ArgumentParser(description='A simple script to flag a wsclean image on')
    parser.add_argument('image', type=str, help='The image that needs to be flagged')
    parser.add_argument('xx_beam', type=str, help='Path to the XX beam used to form the stokes I beam')
    parser.add_argument('yy_beam', type=str, help='Path to the YY beam used to form the stokes I beam')
    parser.add_argument('-a','--apply-mask', action='store_true', default=False, help='Apply the mask to the image. Value is percentage. ')
    parser.add_argument('-l','--level', default=5, type=float, help='Pixels below this primary beam level are flagged')
    parser.add_argument('-v','--verbose', action='store_true', default=False, help='How much logging is needed')

    args = parser.parse_args()

    print(args)

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    derive_apply_beam_cut(
        args.image,
        args.xx_beam,
        args.yy_beam,
        apply_mask=args.apply_mask,
        level=args.level
    )


