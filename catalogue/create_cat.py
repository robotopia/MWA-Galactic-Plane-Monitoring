#!/usr/bin/env python

from astropy.io import fits
from astropy.table import Table, Column
from astropy.coordinates import SkyCoord
from astropy import units as u
import numpy as np

tab = Table(fits.open('all_epochs_comp.fits')[1].data)
coords = SkyCoord(tab['lon'], tab['lat'], frame='galactic', unit=(u.deg, u.deg))
ra, dec = coords.fk5.ra.value, coords.fk5.dec.value

strcoords = coords.fk5.to_string('hmsdms', sep=':', precision=0)
Names = ["GPM J{0}".format(sc.replace(' ', '')) for sc in strcoords]

outtable = Table()
outtable.add_column(Column(data = Names, name = 'Name'))
outtable.add_column(Column(data = ra, name = 'RAJ2000'))
outtable.add_column(Column(data = dec, name = 'DEJ2000'))
outtable.add_column(Column(data = tab['peak_flux'], name = 'S_200'))
outtable.add_column(Column(data = -0.83 * np.ones(len(tab['peak_flux'])), name = 'alpha'))
outtable.add_column(Column(data = np.zeros(len(tab['peak_flux'])), name = 'beta'))
outtable.add_column(Column(data = tab['a'], name = 'a'))
outtable.add_column(Column(data = tab['b'], name = 'b'))
outtable.add_column(Column(data = tab['pa'], name = 'pa'))

outtable.write('GPSM.fits', format = 'fits')
