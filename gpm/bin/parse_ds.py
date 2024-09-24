#!/usr/bin/env python

import argparse
import datetime
import sys
import numpy as np
from casacore.tables import *
from astropy.time import Time
from astropy.coordinates import SkyCoord, Angle, EarthLocation
from astropy import units as u
import h5py
import pickle
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from scipy.signal import medfilt
from scipy import optimize

XX = 0
XY = 1
YX = 2
YY = 3
# HACK for two-pol data
#XX = 0
#XY = 1
#YX = 1
#YY = 1

def time_str(t):
    t_val = Time(t/60.0/60.0/24.0, format='mjd', scale='utc')
    t_val.format='iso'
    return "%s" %(t_val)

class DynamicSpectraMS:
    def __init__(self, ms):
        self.ms = ms
        self.obs_data = {}
        
        # Read antenna-based information
        ta = table("%s/ANTENNA" %(ms))
        self.obs_data["ANT_LIST"] = ta.getcol("STATION")
        self.obs_data["ANT_POS"] = ta.getcol("POSITION")
        self.obs_data["NANT"] = len(self.obs_data["ANT_POS"])
        self.obs_data["NBL"] = int((self.obs_data["NANT"] / 2) * (self.obs_data["NANT"] - 1))
        ta.close()
        # Get the telescope
        ta = table("%s/OBSERVATION" %(ms))
        self.obs_data["TELESCOPE"] = ta.getcol("TELESCOPE_NAME")[0]
        ta.close()
        # Read channel-based information
        tf = table("%s/SPECTRAL_WINDOW" %(ms))
        self.obs_data["FREQS"] = tf[0]["CHAN_FREQ"]
        self.obs_data["NCHAN"] = len(self.obs_data["FREQS"])
        tf.close()
        # Read time data
        t = table(ms)
        # Select only the first set of autos so that we can get all the unique times, the number of integrations and the number of polarisations
        t1 = taql("select from $t where (ANTENNA1==0) && (ANTENNA2==0)")
        self.obs_data["TIMES"] = t1.getcol('TIME')
        self.obs_data["NINT"] = len(self.obs_data["TIMES"])
        first_vis = t1.getcol("DATA", 0, 1)
        self.obs_data["NPOL"] = first_vis.shape[2]
        t1.close()
        # Find number of antennas actualy available in the MS
        t1 = taql("select from $t where (ANTENNA1!=ANTENNA2)")
        antenna1 = t1.getcol("ANTENNA1")
        antenna2 = t1.getcol("ANTENNA2")
        
        avail_ant = np.unique(np.vstack((antenna1, antenna2)))
        missing_ants = []
        for ant in range(self.get_nant()):
           if ant in avail_ant:
              continue
           missing_ants.append(ant)
        self.obs_data["MISSING_ANTS"] = missing_ants
        self.obs_data["NANT_AVAIL"] = len(avail_ant)
        self.obs_data["NBL_AVAIL"] = int((self.obs_data["NANT_AVAIL"] / 2) * (self.obs_data["NANT_AVAIL"] - 1))
        self.obs_data["POLS"] = ["XX", "XY", "YX", "YY"]
        t1.close()
        t.close()
        self.summary()

    # Antenna-based helper functions
    def get_bl(self, a1, a2):
        return np.sqrt((self.obs_data["ANT_POS"][a1,0] - self.obs_data["ANT_POS"][a2,0]) ** 2.0 + (self.obs_data["ANT_POS"][a1,1] - self.obs_data["ANT_POS"][a2,1]) ** 2.0)

    def get_nant(self):
        return self.obs_data["NANT"]

    def get_nant_avail(self):
        return self.obs_data["NANT_AVAIL"]

    def get_nbl(self):
        return self.obs_data["NBL"]
        
    def get_nbl_avail(self):
        return self.obs_data["NBL_AVAIL"]
        
    # Channel-based helper functions
    def get_nchan(self):
        return self.obs_data["NCHAN"]

    def get_freqs(self):
        return self.obs_data["FREQS"]
    
    def get_fmin(self):
        return np.min(self.get_freqs())

    def get_fmax(self):
        return np.max(self.get_freqs())

    def get_bw(self):
        return self.get_fmax()-self.get_fmin()
        
    # Visibility helper functions
    def get_nint(self):
        return self.obs_data["NINT"]
        
    def get_times(self):
        return self.obs_data["TIMES"]
    
    def get_tmin(self):
        return np.min(self.get_times())

    def get_tmax(self):
        return np.max(self.get_times())

    def get_npol(self):
        return self.obs_data["NPOL"]
        
    def get_pols(self):
        return self.obs_data["POLS"]

    def get_stations(self):
        return self.obs_data["ANT_LIST"]

    def summary(self):
        print("Summary of observation:")
        print("%d channels (%.3f-%.3f MHz)" %(self.get_nchan(), self.get_fmin()/1.0e6, self.get_fmax()/1.0e6))

        print("Antennas: %d" %(self.get_nant()))
        print("Missing antennas: ", self.obs_data["MISSING_ANTS"])
        print("%d available antennas" %(self.get_nant_avail()))
        print("Baselines: %d" %(self.get_nbl_avail()))
        print("Visibilities: %d" %(self.get_nint() * self.get_nbl_avail() * self.get_nchan() * self.get_npol()))
        print("Integrations: %d (%s - %s)" %(self.get_nint(), time_str(self.get_tmin()), time_str(self.get_tmax())))
        print("Channels: %d" %(self.get_nchan()))
        print("Polarisations: %d\n" %(self.get_npol()))

    def dump_obs_data(self, output):
        fout = open(output, "wb")
        pickle.dump(self.obs_data, fout)
        fout.close()
        
    # Generate the dynamic spectra from the measurement set
    def process(self, ms=None, min_bl=0.0, data_column = "DATA", max_mem = 1e9, output = None, subtract=False, keepants=None):
        XX=0
        XY=1
        YX=2
        YY=3
        # HACK for two-pol data
#        XX = 0
#        XY = 1
#        YX = 1
#        YY = 1

        if output is None:
            output = ms.replace(".ms", "_ds.pkl")

        if subtract is True:
            print("Will subtract MODEL_DATA column.")

        # Get the dimensions of the visibility data
        nant = self.get_nant()
        nbl = self.get_nbl_avail()
        nint = self.get_nint()
        nchan = self.get_nchan()
        npol = self.get_npol()
        stations = self.get_stations()
        
        nvis = nbl * nint
        self.dump_obs_data(output)
        
        t = table(ms)
# Here is where we need to remove the non-PTUSE antennas
        t1_str = "select from $t where ANTENNA1 != ANTENNA2"
        cmds = []
        if keepants is not None:
            for i, v in enumerate(stations):
                for station in keepants:
                    if station in v:
                        cmds.append("ANTENNA1=={0}".format(i))

        if len(cmds) > 0:
            t1_str += " AND (" + " OR ".join(cmds) + ")"

        t1 = taql(t1_str)

        # read a single visibility to get an idea of how much memory it consumes
        firstvis = t1.getcol(data_column, startrow=1, nrow=1)
        vis_size = sys.getsizeof(firstvis) * nbl # multiple by the number of baselines because that is the smallest quanta we can read
        print("Size of single integration = %d bytes" %(vis_size))
        chunk_size = int(max_mem / vis_size) * nbl
        if chunk_size > nvis:
            chunk_size = nvis
        print("Reading %d visibilities per chunk" %(chunk_size))

        # Read visibility data in chunks to avoid utilising too much memory
        for row in range(0, nvis, chunk_size):
            print("\nProcessing row %d" %(row))
            nremaining = nvis - row
            
            print(" - Reading visibilities")
            if nremaining >= chunk_size:
                vis_ant1 = t1.getcol("ANTENNA1", startrow=row, nrow=chunk_size)
                vis_ant2 = t1.getcol("ANTENNA2", startrow=row, nrow=chunk_size)
                vis_data = t1.getcol(data_column, startrow=row, nrow=chunk_size)
                if subtract is True:
                    model_data = t1.getcol("MODEL_DATA", startrow=row, nrow=chunk_size)
                vis_flag = t1.getcol("FLAG", startrow=row, nrow=chunk_size)
                nvis_read = chunk_size
            else:
                vis_ant1 = t1.getcol("ANTENNA1", startrow=row, nrow=nremaining)
                vis_ant2 = t1.getcol("ANTENNA2", startrow=row, nrow=nremaining)
                vis_data = t1.getcol(data_column, startrow=row, nrow=nremaining)
                if subtract is True:
                    model_data = t1.getcol("MODEL_DATA", startrow=row, nrow=nremaining)
                vis_flag = t1.getcol("FLAG", startrow=row, nrow=nremaining)
                nvis_read = nremaining
            nint_read = int(nvis_read / nbl)
            nvis_all = nvis_read * nchan * npol
            print(" - Read %d integrations; %d visibilities - Flagged = %.1f%%" %(nint_read, nvis_read * nchan * npol, 100.0*np.count_nonzero(vis_flag) / nvis_all))
            # Flag NaNs
            vis_flag[np.where(np.isnan(vis_data))] = True
            print(" - Flag Nans - Flagged = %d / %d" %(np.count_nonzero(vis_flag), nvis_all))
            
            # Flag zeroed data
            vis_flag[np.where(vis_data== 0.0+0.0j)] = True
            print(" - Flag zeroed data - Flagged = %d / %d" %(np.count_nonzero(vis_flag), nvis_all))

            # Flag short baselines
#            for ant1 in range(nant - 1):
#                for ant2 in range(ant1 + 1, nant):
#                    bl_length = self.get_bl(ant1, ant2)
#                    if bl_length < min_bl:
#                        vis_flag[np.where((vis_ant1 == ant1) & (vis_ant2 == ant2)),:,:] = True
#            print(" - Flagging short baselines - Flagged %.1f%%" %(100.0*np.count_nonzero(vis_flag) / nvis_all))
#
            # Flag integrations where number of baselines is too low
            # Count numer of flagged baselines
#            vis_flag = vis_flag.reshape((nint_read, nbl * nchan * npol))
#            flagged = np.count_nonzero(vis_flag, axis=1) > (nbl * nchan * npol/2)
#            vis_flag[flagged,:] = True
#            vis_flag = vis_flag.reshape(nint_read * nbl, nchan, npol)
#
#            print(" - Flagging integrations with significant flagging - Flagged = %.1f%%" %(100.0 * np.count_nonzero(vis_flag) / nvis_all))
#
#            vis_flag[:,:,XX] = np.logical_or(vis_flag[:,:,XX], np.logical_or(vis_flag[:,:,XY], np.logical_or(vis_flag[:,:,YX], vis_flag[:,:,YY])))
#            vis_flag[:,:,XY] = vis_flag[:,:,XX]
#            vis_flag[:,:,YX] = vis_flag[:,:,XX]
#            vis_flag[:,:,YY] = vis_flag[:,:,XX]

            print(" - Spread visibility flagging across all instrumental polarisations - Flagged = %.1f%%" %(100.0*np.count_nonzero(vis_flag) / nvis_all))
            
            # Apply flags
            if data_column != "MODEL_DATA":
                vis_data[np.where(vis_flag==True)] = np.nan



            # Subtract the model, if applicable
            if subtract is True:
                vis_data = vis_data - model_data

            # Reshape the data
            vis_data = vis_data.reshape((nint_read, nbl, nchan, npol))
            
            print(" - Collapsing baselines for block of visibilities read")
            if row == 0:
                # First row so we don't have any values
                self.obs_data["DS_STD"] = np.nanstd(vis_data, axis=1)
                self.obs_data["DS_MED"] = np.nanmedian(vis_data, axis=1)
                self.obs_data["DS"] = np.nanmean(vis_data, axis=1)
            else:
                # We already had a previous block of visibilities, so stack the new set onto the previous
                self.obs_data["DS_STD"] = np.vstack([self.obs_data["DS_STD"], np.nanstd(vis_data, axis=1)])
                self.obs_data["DS_MED"] = np.vstack([self.obs_data["DS_MED"], np.nanmedian(vis_data, axis=1)])
                self.obs_data["DS"] = np.vstack([self.obs_data["DS"], np.nanmean(vis_data, axis=1)])
            print(" - DS shape=", self.obs_data["DS"].shape)
        # Write the DS to files
        self.dump_obs_data(output)

def std_iqr(x):
    """Robust estimation of the standard deviation, based on the inter-quartile
    (IQR) distance of x.
    This computes the IQR of x, and applies the Gaussian distribution
    correction, making it a consistent estimator of the standard-deviation
    (when the sample looks Gaussian with outliers).

    Parameters
    ----------
    x : `np.ndarray`
        Input vector

    Returns
    -------
    output : `float`
        A robust estimation of the standard deviation
    """
    from scipy.stats import iqr
    from scipy.special import erfinv
    good = x[np.where(np.isnan(x)==False)]
    correction = 2 ** 0.5 * erfinv(0.5)
    return correction * iqr(good) 

def time_str(t):
    t_val = Time(t/60.0/60.0/24.0, format='mjd', scale='utc')
    t_val.format='iso'
    return "%s" %(t_val)

# Perform RM-synthesis on Stokes Q and U data
#
# dataQ, dataU and freqs - contains the Q/U data at each frequency (in Hz) measured.
# startPhi, dPhi - the starting RM (rad/m^2) and the step size (rad/m^2)
def getFDF(dataQ, dataU, freqs, startPhi, stopPhi, dPhi, dType='float32'):
    # Calculate the RM sampling
    phiArr = np.arange(startPhi, stopPhi, dPhi)

    # Calculate the frequency and lambda sampling
    lamSqArr = np.power(2.99792458e8 / np.array(freqs), 2.0)

    # Calculate the dimensions of the output RM cube
    nPhi = len(phiArr)

    # Initialise the complex Faraday Dispersion Function (FDF)
    FDF = np.ndarray((nPhi), dtype='complex')

    # Assume uniform weighting
    wtArr = np.ones(len(lamSqArr), dtype=dType)

    K = 1.0 / np.nansum(wtArr)

    # Get the weighted mean of the LambdaSq distribution (B&dB Eqn. 32)
    lam0Sq = K * np.nansum(lamSqArr)

    # Mininize the number of inner-loop operations by calculating the
    # argument of the EXP term in B&dB Eqns. (25) and (36) for the FDF
    a = (-2.0 * 1.0j * phiArr)
    b = (lamSqArr - lam0Sq) 
    arg = np.exp( np.outer(a, b) )

    # Create a weighted complex polarised surface-brightness cube
    # i.e., observed polarised surface brightness, B&dB Eqns. (8) and (14)
    Pobs = (np.array(dataQ) + 1.0j * np.array(dataU))

    # Calculate the Faraday Dispersion Function
    # B&dB Eqns. (25) and (36)
    FDF = K * np.nansum(Pobs * arg, 1)
    return FDF, phiArr

def findpeaks(freqs, fdf, phi, rmsf, rmsfphi, nsigma):
    # Create the Gaussian filter for reconstruction
    c = 299792458.0 # Speed of light
    lam2 = (c / freqs) ** 2.0
    lam02 = np.mean(lam2)
    minl2 = np.min(lam2)
    maxl2 = np.max(lam2)
    width = (2.0 * np.sqrt(3.0)) / (maxl2 - minl2)

    Gauss = np.exp((-rmsfphi ** 2.0) / (2.0 * ((width / 2.355) ** 2.0)))
    components = np.zeros((len(phi)), np.float32)
    peaks = []
    phis = []
    std = 0.0
    rmsflen = int((len(rmsf) - 1) / 2)
    fdflen = len(phi) + rmsflen
    std = np.std(np.abs(fdf))
    peak1 = np.max(np.abs(fdf))
    pos1 = np.argmax(np.abs(fdf))
    val1 = phi[pos1]
    if peak1 > nsigma * std :
        fdf -= rmsf[rmsflen - pos1:fdflen - pos1] * fdf[pos1]
        peaks.append(peak1)
        phis.append(val1)
        components[pos1] += peak1
        std = np.std(np.abs(fdf))
    fdf += np.convolve(components, Gauss, mode='valid')
    return phis, peaks, std

def fitPL(fdata, sdata, serr):
#    print('Running power-law fit:')
    good = np.where(np.isnan(sdata)==False)
    sdata = sdata[good]
    fdata = fdata[good]
    serr = serr[good]
    lognu = np.log10(fdata)
    logs = np.log10(sdata)

    logserr = serr
    # define our (line) fitting function
    fitfunc = lambda p, x: p[0] + p[1] * x
    errfunc = lambda p, x, y, err: (y - fitfunc(p, x)) / err
    pinit = [1.0, -1.0]
    out = optimize.leastsq(errfunc, pinit, args=(lognu, logs, logserr), full_output=1)
    pfinal = out[0]
    covar = out[1]

    index = pfinal[1]
    amp = 10.0**pfinal[0]

    indexErr = np.sqrt( covar[1][1] )
    ampErr = np.sqrt( covar[0][0] ) * amp

    print("   S_0=%f(+/-%f) alpha=%f(+/-%f)" %(amp, ampErr, index, indexErr))
    print(amp,index)
    return amp, index #, (ampErr, indexErr))

def FourierShift(x, delta):
    # The size of the matrix.
    N = len(x)
    
    # FFT of our possibly padded input signal.
    X = np.fft.fft(x)
    
    # The mathsy bit. The floors take care of odd-length signals.
    x_arr = np.hstack([np.arange(np.floor(N/2), dtype=np.int), np.arange(np.floor(-N/2), 0, dtype=np.int)])

    x_shift = np.exp(-1j * 2 * np.pi * delta * x_arr / N)

#    x_shift = x_shift[None, :]   # Shape = (1, N)
    
    # Force conjugate symmetry. Otherwise this frequency component has no
    # corresponding negative frequency to cancel out its imaginary part.
    if np.mod(N, 2) == 0:
        x_shift[N//2] = np.real(x_shift[N//2])

    X = X * x_shift
    
    # Invert the FFT.
    xs = np.fft.ifft(X)
    
    # There should be no imaginary component (for real input
    # signals) but due to numerical effects some remnants remain.
    if np.isrealobj(x):
        xs = np.real(xs)
    
    return xs
    
class DynamicSpectraPKL:
    def __init__(self, pickle_file, pbcorX=1.0, pbcorY=1.0, calCASA=True, ASKAPpolaxis=-45.0, swapASKAPXY=True, use_raw=False):
        print("Loading data from {0}".format(pickle_file))
        obs_data = np.load("%s" %(pickle_file), allow_pickle=True, encoding='bytes')
        self.telescope = obs_data["TELESCOPE"]
        self.nchan = obs_data["NCHAN"]
        self.nint = obs_data["NINT"]
        self.nant = obs_data["NANT"]
        self.npol = obs_data["NPOL"]
        self.pols = obs_data["POLS"]
        self.ant_pos = obs_data["ANT_POS"]
        self.ant_list = obs_data["ANT_LIST"]
        self.nant_avail = obs_data["NANT_AVAIL"]
        self.nbl = obs_data["NBL"]
        self.nbl_avail = obs_data["NBL_AVAIL"]
        self.freqs = obs_data["FREQS"] # frequency channels in Hz
        self.times = obs_data["TIMES"] # time stamps in seconds
        self.missing_ants = obs_data["MISSING_ANTS"]
        # Correct for primary beam at source location (if known)
        self.ds_std = obs_data["DS_STD"]
        self.ds_std[:,:,XX] /= (pbcorX*pbcorX)
        self.ds_std[:,:,XY] /= (pbcorX*pbcorY)
        self.ds_std[:,:,YX] /= (pbcorY*pbcorX)
        self.ds_std[:,:,YY] /= (pbcorY*pbcorY)
        self.ds_med = obs_data["DS_MED"]
        self.ds_med[:,:,XX] /= (pbcorX*pbcorX)
        self.ds_med[:,:,XY] /= (pbcorX*pbcorY)
        self.ds_med[:,:,YX] /= (pbcorY*pbcorX)
        self.ds_med[:,:,YY] /= (pbcorY*pbcorY)
        self.ds = obs_data["DS"]
        self.ds[:,:,XX] /= (pbcorX*pbcorX)
        self.ds[:,:,XY] /= (pbcorX*pbcorY)
        self.ds[:,:,YX] /= (pbcorY*pbcorX)
        self.ds[:,:,YY] /= (pbcorY*pbcorY)
        self.pbcorX = pbcorX
        self.pbcorY = pbcorY
        self.tintms = np.median(self.times[1:] - self.times[:-1])*1000.0 # integration time in mS
        self.calCASA = calCASA
        self.polaxis = ASKAPpolaxis
        self.swapASKAPXY = swapASKAPXY
        self.use_raw = use_raw
        

    def summary(self):
        print("Summary of observation:")
        print("Telescope: %s" %(self.telescope))
        print("%d channels (%.3f-%.3f MHz)" %(self.nchan, np.min(self.freqs)/1.0e6, np.max(self.freqs)/1.0e6))

        print("Antennas: %d" %(self.nant))
        print("Missing antennas: ", self.missing_ants)
        print("%d available antennas" %(self.nant_avail))
        print("Baselines: %d" %(self.nbl_avail))
        print("Visibilities: %d" %(self.nint * self.nbl_avail * self.nchan * self.npol))
        print("Integrations: %d (%s - %s)" %(self.nint, time_str(np.min(self.times)), time_str(np.max(self.times))))
        print("Integration time: %.1f mS" %(self.tintms))
        print("Channels: %d" %(self.nchan))
        print("Polarisations: %d\n" %(self.npol))

    def bary_time(self, direction):
        ASKAP_longitude = Angle("116:38:13.0", unit=u.deg)
        ASKAP_latitude = Angle("-26:41:46.0", unit=u.deg)
        ASKAP_location = EarthLocation(lat=ASKAP_latitude, lon=ASKAP_longitude)
        ASKAP_alt = 0.0

        MeerKAT_longitude = Angle("21:19:48.0", unit=u.deg)
        MeerKAT_latitude = Angle("-30:49:48.0", unit=u.deg)
        MeerKAT_location = EarthLocation(lat=MeerKAT_latitude, lon=MeerKAT_longitude)
        MeerKAT_alt = 0.0
        
        if self.telescope == "ASKAP" or self.telescope == "MWA":
            ut = Time(self.times/60.0/60.0/24.0, format='mjd', scale='utc', location=ASKAP_location)
        elif self.telescope == "MEERKAT":
            ut = Time(self.times/60.0/60.0/24.0, format='mjd', scale='utc', location=MeerKAT_location)

        ltt_bary = ut.light_travel_time(direction, ephemeris='jpl') # Convert to barycentric time
        batc = ut.tdb + ltt_bary
        bat_mjd = batc.value
        return bat_mjd

    def mjd_time(self):
        ut = Time(self.times/60.0/60.0/24.0, format='mjd', scale='utc')
        return ut

    def dedisperse(self, DM = 0.0):
        # delay in mS; frequency in GHz
        dt_ms = 4.149 * DM *(1.0/np.power(self.freqs[-1]/1.0e9, 2.0) - 1.0/np.power(self.freqs/1.0e9, 2.0))
        dint = dt_ms / self.tintms # convert to samples
        # de-disperse
        for chan in range(self.nchan):
            for pol in [XX, XY, YX, YY]:
#                print(self.freqs[chan], "GHz", self.pols[pol], dt[chan])
#                print(self.ds[:,chan,pol])
                self.ds[:,chan,pol][np.where(np.isnan(self.ds[:,chan,pol]) == True)] = 0.0
                self.ds[:,chan,pol] = FourierShift(self.ds[:,chan,pol], dint[chan])
#                print("%.3f MHz, %.1f sample shift" %(self.freqs[chan]/1.0e6, dint[chan]))
#                print(self.ds[:,chan,pol])
#                offset = dt[self.nchan-chan - 1]
#                if offset == 0:
#                    continue
#                self.ds[:-offset,chan,pol] = self.ds[offset:,chan,pol]
    
    # Average over aT integrations and aF channels.
    # NOTE: this is a very rudimentary form of averaging and does not consider gaps between integrations.
    def average(self, aT = 1, aF = 1):
        print("Original", self.ds.shape)
        nchan = self.nchan
        if (self.nchan % aF) != 0:
            # Spectrum doesn't divide up nicely, need to crop a bit
            naver = int(self.nchan / aF)
            nchan = int(naver * aF)
            self.ds = self.ds[:,:nchan,:]
            self.ds_std = self.ds_std[:,:nchan,:]
            self.ds_med = self.ds_med[:,:nchan,:]
            self.freqs = self.freqs[:nchan]
        nint = self.nint
        print("Freq adjusted size: ",self.ds.shape)
        if (self.nint % aT) != 0:
            # Times don't divide up nicely, need to crop a bit
            naver = int(self.nint / aT)
            nint = int(naver * aT)
            self.ds = self.ds[:nint,:,:]
            self.ds_std = self.ds_std[:nint,:,:]
            self.ds_med = self.ds_med[:nint,:,:]
            self.times = self.times[:nint]
        print("Time adjusted size: ", self.ds.shape)
        # Prepare axis labels for averaged data
        self.freqs = np.nanmean(self.freqs.reshape(int(self.nchan/aF), aF), axis=1)
        self.times = np.nanmean(self.times.reshape(int(self.nint/aT), aT), axis=1)
        self.nchan = nchan
        self.nint = nint
        # Average channels
        ds_aver_freq = np.nanmean(self.ds.reshape((self.nint, int(self.nchan/aF), aF, self.npol)), axis=2)
        print("Freq averaged size: ",self.ds.shape)
        ds_aver_freq_std = np.nanmean(self.ds_std.reshape((self.nint, int(self.nchan/aF), aF, self.npol)), axis=2)
        ds_aver_freq_med = np.nanmean(self.ds_med.reshape((self.nint, int(self.nchan/aF), aF, self.npol)), axis=2)
        # Average times
        self.ds = np.nanmean(ds_aver_freq.reshape((int(self.nint/aT), aT, int(self.nchan/aF), self.npol)), axis=1)
        print("Time averaged size: ",self.ds.shape)
        self.ds_std = np.nanmean(ds_aver_freq_std.reshape((int(self.nint/aT), aT, int(self.nchan/aF), self.npol)), axis=1)
        self.ds_med = np.nanmean(ds_aver_freq_med.reshape((int(self.nint/aT), aT, int(self.nchan/aF), self.npol)), axis=1)
        self.nchan = int(self.nchan/aF)
        self.nint = int(self.nint/aT)
        
    def get_stokes(self):
        if self.use_raw:
            It = np.real((self.ds[:,:,XX]+self.ds[:,:,YY]))
            Qt = np.real((self.ds[:,:,XX]-self.ds[:,:,YY]))
            Ut = np.real((self.ds[:,:,XY]+self.ds[:,:,YX]))
            Vt = np.imag((self.ds[:,:,XY]-self.ds[:,:,YX]))
            return It, Qt, Ut, Vt
            
        if (self.telescope == "ASKAP") and (self.calCASA == False): # ASKAP calibrated
            print("Assuming ASKAP calibrated data")
            theta = 2.0 * np.radians(self.polaxis)
            if self.swapASKAPXY:
                print("Swapping X and Y")
                It = np.real((self.ds[:,:,YY]+self.ds[:,:,XX]))
                Qt = np.real(np.cos(theta)*(self.ds[:,:,YX]+self.ds[:,:,XY]) - np.sin(theta)*(self.ds[:,:,YY]-self.ds[:,:,XX]))
                Ut = np.real(np.sin(theta)*(self.ds[:,:,YX]+self.ds[:,:,XY]) + np.cos(theta)*(self.ds[:,:,YY]-self.ds[:,:,XX]))
                Vt = np.imag((self.ds[:,:,YX]-self.ds[:,:,XY]))
            else:
                It = np.real((self.ds[:,:,XX]+self.ds[:,:,YY]))
                Qt = np.real(np.cos(theta)*(self.ds[:,:,XY]+self.ds[:,:,YX]) - np.sin(theta)*(self.ds[:,:,XX]-self.ds[:,:,YY]))
                Ut = np.real(np.sin(theta)*(self.ds[:,:,XY]+self.ds[:,:,YX]) + np.cos(theta)*(self.ds[:,:,XX]-self.ds[:,:,YY]))
                Vt = np.imag((self.ds[:,:,XY]-self.ds[:,:,YX]))
                
        elif (self.telescope == "ASKAP") and (self.calCASA == True): # CASA calibrated
            print("Using CASA calibrated data")
            theta = 2.0 * np.radians(self.polaxis)
            if self.swapASKAPXY:
                print("Swapping X and Y")
                It = np.real((self.ds[:,:,YY]+self.ds[:,:,XX]))/2.0
                Qt = np.real(np.cos(theta)*(self.ds[:,:,YX]+self.ds[:,:,XY]) - np.sin(theta)*(self.ds[:,:,YY]-self.ds[:,:,XX]))/2.0
                Ut = np.real(np.sin(theta)*(self.ds[:,:,YX]+self.ds[:,:,XY]) + np.cos(theta)*(self.ds[:,:,YY]-self.ds[:,:,XX]))/2.0
                Vt = np.imag((self.ds[:,:,YX]-self.ds[:,:,XY])/2.0)
            else:
                It = np.real((self.ds[:,:,XX]+self.ds[:,:,YY]))/2.0
                Qt = np.real(np.cos(theta)*(self.ds[:,:,XY]+self.ds[:,:,YX]) - np.sin(theta)*(self.ds[:,:,XX]-self.ds[:,:,YY]))/2.0
                Ut = np.real(np.sin(theta)*(self.ds[:,:,XY]+self.ds[:,:,YX]) + np.cos(theta)*(self.ds[:,:,XX]-self.ds[:,:,YY]))/2.0
                Vt = np.imag((self.ds[:,:,XY]-self.ds[:,:,YX])/2.0)
        elif self.telescope == "MWA": # CASA calibrated
            It = np.real((self.ds[:,:,XX]+self.ds[:,:,YY])/2.0)
            Qt = np.real((self.ds[:,:,XX]-self.ds[:,:,YY])/2.0)
            Ut = np.real((self.ds[:,:,XY]+self.ds[:,:,YX])/2.0)
            Vt = np.imag((self.ds[:,:,XY]-self.ds[:,:,YX])/2.0)
        elif self.telescope == "MeerKAT": # CASA calibrated
            It = np.real((self.ds[:,:,XX]+self.ds[:,:,YY])/2.0)
            Qt = np.real((self.ds[:,:,XX]-self.ds[:,:,YY])/2.0)
            Ut = np.real((self.ds[:,:,XY]+self.ds[:,:,YX])/2.0)
            Vt = np.imag((self.ds[:,:,XY]-self.ds[:,:,YX])/2.0)
        elif self.telescope == "GMRT": # CASA calibrated
            It = np.real((self.ds[:,:,XX]+self.ds[:,:,YY])/2.0)
            Qt = np.real((self.ds[:,:,XX]-self.ds[:,:,YY])/2.0)
            Ut = np.real((self.ds[:,:,XY]+self.ds[:,:,YX])/2.0)
            Vt = np.imag((self.ds[:,:,XY]-self.ds[:,:,YX])/2.0)
        return It, Qt, Ut, Vt

    def flagNoisyVChannels(self, nsigma):
        It, Qt, Ut, Vt = self.get_stokes()
        vstd = np.nanstd(Vt, axis=0)
        bad_chans = np.where(vstd > (nsigma * np.nanmedian(vstd)))
        for chan in bad_chans[0]:
            print("flag channel %d" %(chan))
            self.ds[:,chan,XX] = np.nan
            self.ds[:,chan,XY] = np.nan
            self.ds[:,chan,YX] = np.nan
            self.ds[:,chan,YY] = np.nan

    # Flag based on Stokes V extremes (usually a good indicator of RFI in the absense of true circular polarisation)
    def flagV(self, nsigma = 3.0):
        It, Qt, Ut, Vt = self.get_stokes()
        vstd = np.nanstd(Vt)
        bad = np.where(np.abs(Vt) > nsigma*vstd)
        self.ds[:,:,XX][bad] = np.nan
        self.ds[:,:,XY][bad] = np.nan
        self.ds[:,:,YX][bad] = np.nan
        self.ds[:,:,YY][bad] = np.nan
        
        for chan in range(self.nchan):
            frac = float(np.sum(np.isnan(self.ds[:,chan,XX])))/float(self.nchan)
            if frac > 0.05:
                print("ods.flag_chan(%d,%d)" %(chan, chan))

    # Flag based on Stokes V extremes (usually a good indicator of RFI in the absense of true circular polarisation)
    def flagQU(self, nsigma = 3.0):
        It, Qt, Ut, Vt = self.get_stokes()
        qstd = np.nanstd(Qt)
        bad = np.where(np.abs(Qt) > nsigma*qstd)
        self.ds[:,:,XX][bad] = np.nan
        self.ds[:,:,XY][bad] = np.nan
        self.ds[:,:,YX][bad] = np.nan
        self.ds[:,:,YY][bad] = np.nan
        ustd = np.nanstd(Ut)
        bad = np.where(np.abs(Ut) > nsigma*ustd)
        self.ds[:,:,XX][bad] = np.nan
        self.ds[:,:,XY][bad] = np.nan
        self.ds[:,:,YX][bad] = np.nan
        self.ds[:,:,YY][bad] = np.nan
        
    # Flag based on Stokes V extremes (usually a good indicator of RFI in the absense of true circular polarisation)
    def flagI(self, nsigma = 3.0):
        It, Qt, Ut, Vt = self.get_stokes()
        istd = np.nanstd(It)
        bad = np.where(np.abs(It) > nsigma*istd)
        self.ds[:,:,XX][bad] = np.nan
        self.ds[:,:,XY][bad] = np.nan
        self.ds[:,:,YX][bad] = np.nan
        self.ds[:,:,YY][bad] = np.nan
        
    # Flag channel range from channel c1 to c2
    def flag_chan(self, c1, c2):
        self.ds[:,c1:c2,:] = np.nan
        
    # Flag channel range from channel c1 to c2
    def flag_time(self, t1, t2):
        self.ds[t1:t2,:,:] = np.nan

    # Flag channel range from channel c1 to c2
    def flag_window(self, t1, t2, c1, c2):
        self.ds[t1:t2,c1:c2,:] = np.nan

    def get_lc(self):
        I, Q, U, V = self.get_stokes()
        averI = np.nanmean(I, axis=1)  # Average DS in frequency
        return averI

    # Plot the time-series light curve averaged over the band
    def plot_rawsed(self, t):
        xx = self.ds[t,:,XX]
        yy = self.ds[t,:,YY]
        stdI = np.nanstd(xx)
        print(np.nanmean(np.real(xx+yy)))
        fig = plt.figure(figsize=(7, 5))
        ax1 = fig.add_subplot(111)
        plot, = ax1.plot(self.freqs/1.0e9, np.real(xx), marker='', color="black", label="XX")
        plot, = ax1.plot(self.freqs/1.0e9, np.real(yy), marker='', color="red", label="YY")
        plot, = ax1.plot(self.freqs/1.0e9, np.real(xx+yy), marker='', color="green", label="XX+YY")
        plot, = ax1.plot(self.freqs/1.0e9, np.real(xx-yy), marker='', color="blue", label="XX-YY")
        ax1.set_title("Raw light Curve")
        ax1.set_xlabel("Integration")
        ax1.set_ylabel("Flux Density (mJy)")
        plt.legend()
        plt.tight_layout()
        plt.show()
        plt.close()

    # Plot the time-series light curve averaged over the band
    def plot_lc(self, nsigma, sub_med=True, real_time=True, ppol = "IQUVP"):
        I, Q, U, V = self.get_stokes()
        P = np.sqrt(Q*Q + U*U)
        averI = np.nanmean(I, axis=1) * 1000.0  # Average DS in frequency and convert to mJy
        averQ = np.nanmean(Q, axis=1) * 1000.0
        averU = np.nanmean(U, axis=1) * 1000.0
        averV = np.nanmean(V, axis=1) * 1000.0

        averP = np.nanmean(P, axis=1) * 1000.0

        stdI = np.nanstd(averI)
        if real_time == True:
            t = self.times - self.times[0]
        else:
            t = range(len(self.times))

        fig = plt.figure(figsize=(7, 5))
        ax1 = fig.add_subplot(111)
        if ppol.find("I") != -1:
            medI = medfilt(averI, 11)
            if sub_med == True:
                plot, = ax1.plot(t, averI - medI, marker='', color="black", label="I")
            else:
                plot, = ax1.plot(t, averI, marker='', color="black", label="I")
        if ppol.find("Q") != -1:
            medQ = medfilt(averQ, 11)
            if sub_med == True:
                plot, = ax1.plot(t, averQ - medQ, marker='', color="red", label="Q")
            else:
                plot, = ax1.plot(t, averQ, marker='', color="red", label="Q")
        if ppol.find("U") != -1:
            medU = medfilt(averU, 11)
            if sub_med == True:
                plot, = ax1.plot(t, averU - medU, marker='', color="blue", label="U")
            else:
                plot, = ax1.plot(t, averU, marker='', color="blue", label="U")
        if ppol.find("V") != -1:
            medV = medfilt(averV, 11)
            if sub_med == True:
                plot, = ax1.plot(t, averV - medV, marker='', color="green", label="V")
            else:
                plot, = ax1.plot(t, averV, marker='', color="green", label="V")
        if ppol.find("P") != -1:
            medP = medfilt(averP, 11)
            if sub_med == True:
                plot, = ax1.plot(t, averP - medP, marker='', color="gray", label="P")
            else:
                plot, = ax1.plot(t, averP, marker='', color="gray", label="P")
        ax1.set_title("Light Curve")
        if real_time == True:
            ax1.set_xlabel("Elapsed time (s)")
        else:
            ax1.set_xlabel("Integration")
        ax1.set_ylabel("Flux Density (mJy)")
        ax1.set_ylim(-nsigma*stdI/6.0, nsigma*stdI)
        print("stdI=%.3f" %(stdI))
        plt.legend()
        plt.tight_layout()
        plt.show()
        plt.close()

    # Plot the time-series light curve averaged over the band
    def lc_peaks(self, nsigma, sub_med=False):
        print(nsigma)
        I, Q, U, V = self.get_stokes()
        P = np.sqrt(Q*Q + U*U)
        averI = np.nanmean(I, axis=1) * 1000.0  # Average DS in frequency and convert to mJy
        averQ = np.nanmean(Q, axis=1) * 1000.0
        averU = np.nanmean(U, axis=1) * 1000.0
        averV = np.nanmean(V, axis=1) * 1000.0
        averP = np.nanmean(P, axis=1) * 1000.0
        if sub_med == True:
            medI = medfilt(averI, 11)
            averI -= medI

        stdI = std_iqr(averI)
        print(stdI, nsigma)
        t = []
        for index in range(len(self.times)):
            if averI[index] > nsigma * stdI:
                t.append(index)
                print("%s,%d,%.3f" %(time_str(self.times[index]), index, averI[index]))
        return t

    # Save the dynamic spectrum to a 2D CSV file
    def save_ds(self, csv=None):
        stokes = ["I", "Q", "U", "V"]
        vals = {}
        vals["I"], vals["Q"], vals["U"], vals["V"] = self.get_stokes()
        for stoke in stokes:
            np.savetxt(csv.replace(".csv","-{0}.csv".format(stoke)), vals[stoke])

    # Save the observation information in a yaml file in our format
    def save_yaml(self, csv=None, yaml=None):
        stokes = ["I", "Q", "U", "V"]
        for stoke in stokes:
            fileout = yaml.replace(".yaml", "-{0}.yaml".format(stoke))
            with open(fileout, "w") as f:
                f.write("Apply barycentric correction: true\n")
                f.write("Dynamic spectrum:\n")
                f.write("  Centre of lowest channel (MHz): {0}\n".format(self.freqs[0]/1.e6))
                f.write("  Channel width (MHz): {0}\n".format((self.freqs[1] - self.freqs[0])/1.e6))
                f.write("  Input file: {0}\n".format(csv.replace(".csv", "-{0}.csv".format(stoke))))
# TODO: introduce some sensible rounding here
                f.write("  Sample time (s): {0}\n".format(self.times[1] - self.times[0]))
# TODO: Are measurement sets definitely in UTC, not TAI?
                f.write("  T0 (s): {0}\n".format(Time(self.times[0]/(60*60*24), scale="utc", format="mjd").gps))
                f.write("  Transpose: true\n")
                f.write("  ObsID: {0}\n".format(str(Time(self.times[0]/(60*60*24), scale="utc", format="mjd").gps)[0:10]))
                f.write("  Reference frequency (MHz): high\n")
                f.write("Telescope: {0}\n".format(self.telescope))
                f.write("RFI Mask:\n")
                f.write("  Value: 0.0\n")
# TODO: get these from the measurement set!
                f.write("RA: 18.6505\n")
                f.write("Dec: -10.5304\n")
                f.write("Padding: DM\n")

    # Plot the dynamic spectra for the four polarisations
    def plot_ds(self, sigma, real_time=False, real_freq=False, outplot=None):
             
        It, Qt, Ut, Vt = self.get_stokes()
        vstd = np.nanstd(Vt)*1.e3

        current_cmap = cm.get_cmap("cubehelix").copy()
        current_cmap.set_bad(color=current_cmap(0.5))
        
        if real_time==False and real_freq==False:
            ext = [0, self.nint, 0, self.nchan]
            tlabel = "Integration"
            flabel = "Chan"
        elif real_time==True and real_freq==False:
            ext = [0.0, self.times[-1]-self.times[0], 0, self.nchan]
            tlabel = "Elapsed Time (s)"
            flabel = "Chan"
        elif real_time==False and real_freq==True:
            tlabel = "Integration"
            flabel = "$\\nu$ (GHz)"
            ext = [0, self.nint, self.freqs[0]/1.e9,self.freqs[-1]/1.e9]
        else:
            ext = [0.0, self.times[-1]-self.times[0], self.freqs[0]/1.e9,self.freqs[-1]/1.e9]
            tlabel = "Elapsed Time (s)"
            flabel = "$\\nu$ (GHz)"

        fig = plt.figure(figsize=(14, 8))
        ax1 = fig.add_subplot(221)
        ax1.set_title("Stokes I")
        ax1.set_xlabel(tlabel)
        ax1.set_ylabel(flabel)
        plt.imshow(np.transpose(It)*1.e3, origin='lower', clim=(0.0, sigma*vstd), extent=ext, aspect="auto", cmap=current_cmap)
        cbar = plt.colorbar()
        cbar.set_label('mJy')#,labelpad=-75)

        ax2 = fig.add_subplot(222)
        ax2.set_title("Stokes Q")
        ax2.set_xlabel(tlabel)
        ax2.set_ylabel(flabel)
        plt.imshow(np.transpose(Qt)*1.e3, origin='lower', clim=(-sigma*vstd, sigma*vstd), extent=ext, aspect="auto", cmap=current_cmap)
        cbar = plt.colorbar()
        cbar.set_label('mJy')#,labelpad=-75)


        ax3 = fig.add_subplot(223)
        ax3.set_title("Stokes U")
        ax3.set_xlabel(tlabel)
        ax3.set_ylabel(flabel)
        plt.imshow(np.transpose(Ut)*1.e3, origin='lower', clim=(-sigma*vstd, sigma*vstd), extent=ext, aspect="auto", cmap=current_cmap)
        cbar = plt.colorbar()
        cbar.set_label('mJy')#,labelpad=-75)

        ax4 = fig.add_subplot(224)
        ax4.set_title("Stokes V")
        ax4.set_xlabel(tlabel)
        ax4.set_ylabel(flabel)
        plt.imshow(np.transpose(Vt)*1.e3, origin='lower', clim=(-sigma*vstd, sigma*vstd), extent=ext, aspect="auto", cmap=current_cmap)
        cbar = plt.colorbar()
        cbar.set_label('mJy')#,labelpad=-75)

        plt.tight_layout()
        if outplot is None:
            plt.show()
            plt.close()
        else:
            plt.savefig(outplot, bbox_inches="tight")
        
    # Plot the dynamic spectra for the four polarisations
    def plot_cpds(self, sigma, sname = "", real_time=False, real_freq=False):
        It, Qt, Ut, Vt = self.get_stokes()
        vstd = np.nanstd(Vt)

        current_cmap = cm.get_cmap("cubehelix").copy()
        current_cmap.set_bad(color=current_cmap(0.5))
        
        if real_time==False and real_freq==False:
            ext = [0, self.nint, 0, self.nchan]
            tlabel = "Integration"
            flabel = "Chan"
        elif real_time==True and real_freq==False:
            ext = [0.0, self.times[-1]-self.times[0], 0, self.nchan]
            tlabel = "Elapsed Time (s)"
            flabel = "Chan"
        elif real_time==False and real_freq==True:
            tlabel = "Integration"
            flabel = "$\\nu$ (GHz)"
            ext = [0, self.nint, self.freqs[0],self.freqs[-1]]
        else:
            ext = [0.0, self.times[-1]-self.times[0], self.freqs[0],self.freqs[-1]]
            tlabel = "Elapsed Time (s)"
            flabel = "$\\nu$ (GHz)"

        fig = plt.figure(figsize=(14, 8))
        ax4 = fig.add_subplot(111)
        ax4.set_title("Dynamic Spectra (V) - %s" %(sname))
        ax4.set_xlabel(tlabel)
        ax4.set_ylabel(flabel)
        plt.imshow(np.transpose(Vt), origin='lower', clim=(-sigma*vstd, sigma*vstd), extent=ext, aspect="auto", cmap=current_cmap)
        cbar = plt.colorbar()
        cbar.set_label('Jy')#,labelpad=-75)

        plt.tight_layout()
        if len(sname):
            plt.savefig("%s.png" %(sname))
        else:
            plt.show()
        plt.close()
        
    # Plot the SED for the given time integration
    def plot_sed(self, t, pols="IQUV", title="SED", plotwl2=False):
        I, Q, U, V = self.get_stokes()
        It = I[t]
        Qt = Q[t]
        Ut = U[t]
        Vt = V[t]
        Pt = np.sqrt(Qt*Qt+Ut*Ut)

        if plotwl2:
            xaxis = np.power(3.0e8/self.freqs, 2.0)
        else:
            xaxis = self.freqs/1.0e9
        fig = plt.figure(figsize=(7, 5))
        ax1 = fig.add_subplot(111)
        if "I" in pols:
            plot, = ax1.plot(xaxis, It*1000.0, marker='', color="black", label="I")
        if "Q" in pols:
            plot, = ax1.plot(xaxis, Qt*1000.0, marker='', color="red", label="Q")
        if "XX" in pols:
            plot, = ax1.plot(xaxis, self.ds[0,:,XX]*1000.0, marker='', color="red", label="XX", ls=":")
        if "YY" in pols:
            plot, = ax1.plot(xaxis, self.ds[0,:,YY]*1000.0, marker='', color="blue", label="YY", ls=":")
        if "U" in pols:
            plot, = ax1.plot(xaxis, Ut*1000.0, marker='', color="blue", label="U")
        if "V" in pols:
            plot, = ax1.plot(xaxis, Vt*1000.0, marker='', color="green", label="V")
        if "P" in pols:
            plot, = ax1.plot(xaxis, Pt*1000.0, marker='', color="gray", label="P")
        ax1.set_title(title)
        if plotwl2:
            ax1.set_xlabel("(m$^{2}$)")
        else:
            ax1.set_xlabel("Frequency (GHz)")
        ax1.set_ylabel("Flux Density (mJy)")
        plt.legend()
        plt.tight_layout()
        plt.show()
        plt.close()
    
    def find_fdf_peaks(self, min_snr = 10.0, startPhi = -1000.0, dPhi = 1.0):
        t_vals = []
        pi_vals = []
        phi_vals = []
        snr_vals = []
        I, Q, U, V = self.get_stokes()
        stopPhi = -startPhi+dPhi

        chanBW = np.median(self.freqs[1:] - self.freqs[:-1])
        C = 299792458   # Speed of light

        fmin = np.min(self.freqs)
        fmax = np.max(self.freqs)
        bw = fmax - fmin

        dlambda2 = np.power(C / fmin, 2) - np.power(C / (fmin + chanBW), 2)
        Dlambda2 = np.power(C / fmin, 2) - np.power(C / (fmin + bw), 2)
        phimax = np.sqrt(3) / dlambda2
        dphi = 2.0 * np.sqrt(3) / Dlambda2
        phiR = dphi / 5.0
        Nphi = 2 * phimax / phiR
        fwhm = dphi
    
        for t in range(self.nint):
            It = I[t]
            Qt = Q[t]
            Ut = U[t]
            Vt = V[t]
            I_mean = np.nanmean(It)

            dirty, phi = getFDF(Qt, Ut, self.freqs, startPhi, stopPhi, dPhi)
            FDFqu, phi = getFDF(Qt, Ut, self.freqs, startPhi, stopPhi, dPhi)
            rstartPhi = startPhi * 2
            rstopPhi = stopPhi * 2 - dPhi
            RMSF, rmsfphi = getFDF(np.ones(Qt.shape), np.zeros(Ut.shape), self.freqs, rstartPhi, rstopPhi, dPhi)

            # Do a very rudimentary clean i.e. find a peak and subtract out the RMSF at that peak
            phis, peaks, sigma = findpeaks(self.freqs, FDFqu, phi, RMSF, rmsfphi, 6.0)
            if len(peaks) > 0:
                snr = peaks[0] / sigma
                if snr > min_snr:
                    t_vals.append(t)
                    pi_vals.append(peaks[0])
                    snr_vals.append(snr)
                    phi_vals.append(phis[0])
#                    print("%s PI=%.3f mJy/beam (SNR %.1f) RM=%.1f" %(time_str(ods.times[t]), 1000.0*peaks[0], snr, phis[0]))
        return np.array(t_vals), np.array(pi_vals), np.array(snr_vals), np.array(phi_vals)

    def get_sed(self, t):
        I, Q, U, V = self.get_stokes()
        It = I[t]
        Qt = Q[t]
        Ut = U[t]
        Vt = V[t]
        return It, Qt, Ut, Vt
        
    def get_sed_aver(self):
        I, Q, U, V = self.get_stokes()
        It = np.nanmean(I, axis=0) 
        Qt = np.nanmean(Q, axis=0) 
        Ut = np.nanmean(U, axis=0) 
        Vt = np.nanmean(V, axis=0) 
        return It, Qt, Ut, Vt
        
    def get_fdf(self, t, startPhi = -1000.0, dPhi = 1.0):
        I, Q, U, V = self.get_stokes()
        It = I[t]
        Qt = Q[t]
        Ut = U[t]
        Vt = V[t]
        I_mean = np.nanmean(It)
        stopPhi = -startPhi+dPhi

        chanBW = np.median(self.freqs[1:] - self.freqs[:-1])
        C = 299792458   # Speed of light

        fmin = np.min(self.freqs)
        fmax = np.max(self.freqs)
        bw = fmax - fmin


        dlambda2 = np.power(C / fmin, 2) - np.power(C / (fmin + chanBW), 2)
        Dlambda2 = np.power(C / fmin, 2) - np.power(C / (fmin + bw), 2)
        phimax = np.sqrt(3) / dlambda2
        dphi = 2.0 * np.sqrt(3) / Dlambda2
        phiR = dphi / 5.0
        Nphi = 2 * phimax / phiR
        fwhm = dphi
        
        dirty, phi = getFDF(Qt, Ut, self.freqs, startPhi, stopPhi, dPhi)
        FDFqu, phi = getFDF(Qt, Ut, self.freqs, startPhi, stopPhi, dPhi)
        rstartPhi = startPhi * 2
        rstopPhi = stopPhi * 2 - dPhi
        RMSF, rmsfphi = getFDF(np.ones(Qt.shape), np.zeros(Ut.shape), self.freqs, rstartPhi, rstopPhi, dPhi)

        # Do a very rudimentary clean i.e. find a peak and subtract out the RMSF at that peak
        phis, peaks, sigma = findpeaks(self.freqs, FDFqu, phi, RMSF, rmsfphi, 6.0)
        return FDFqu, I_mean, phi, phis, peaks, sigma, fwhm

    # Plot the Faraday Dispersion Function for the given time integration
    def plot_fdf(self, t, startPhi = -1000.0, dPhi = 1.0, doplot=False):
        FDFqu, I_mean, phi, phis, peaks, sigma, fwhm = self.get_fdf(t, startPhi, dPhi)
        snr = 0.0
        if len(peaks) > 0:#
            snr = peaks[0] / sigma
            phierr = fwhm / (2 * snr)
            print("%s PI: %.3f mJy/beam Imean=%.3f (SNR=%.1f) phi=%.3f+/-%.1f fp=%.1f%%" %(time_str(self.times[t]), peaks[0]*1000.0, I_mean*1000.0, snr, phis[0], phierr, 100.0*peaks[0] / I_mean))
        if doplot:
            # Plot the RMSF
            fig = plt.figure()
            ax1 = fig.add_subplot(111)
            plot, = ax1.plot(phi, 1000.0*np.abs(FDFqu), marker=None, color="black")
            ax1.set_title("FDF - cleaned")
            ax1.set_xlabel("phi (rad m$^{-2}$)")
            ax1.set_ylabel("Flux (mJy beam$^{-1}$ RMSF$^{-1}$)")
            ax1.set_xlim(phi[0], phi[-1])
            plt.show()
            plt.close()
        return snr

if __name__ == "__main__":
    # Parse the command line
    parser = argparse.ArgumentParser(description='Extract and make plots of a dynamic spectrum from a measurement set')
    parser.add_argument('--ms', type=str, help='Measurement set to use (if not set, will attempt to use file specified in --pickle as input', default=None)
    parser.add_argument('--column', type=str, help='Data column (default=DATA)', default="DATA")
    parser.add_argument('--antennas', type=str, help='Comma-separated list of antenna names to retain (e.g. for MeerKAT: m047,m046,m045... for MWA: Tile111,Tile112,Tile113...)', default=None)
    parser.add_argument('--subtract', action='store_true', help='Subtract the MODEL_DATA column (default = do not subtract)', default=False)
    parser.add_argument('--sigma', type=float, help='Sigma-clipping for the plots (default=3)', default=3.0)
    parser.add_argument('--min_bl', type=float, help='Minimum baseline length in metres (default=0)', default=0.0)
    parser.add_argument('--pickle', type=str, help='The file to which the dynamic spectrum will be written, or, if ms is not set, read from', default=None)
    parser.add_argument('--dscsv', type=str, help='If set, write the measurements to CSV in a 2D time/frequency array as expected by the MWA transients processing', default=None)
    parser.add_argument('--yaml', type=str, help='If set, write the metadata to YAML in the format expected by the MWA transients processing (dscsv must also be set)', default=None)
    parser.add_argument('--outplot', type=str, help='The file to which the dynamic spectrum will be plotted', default=None)

    print("Parsing args at", datetime.datetime.now())
    args = parser.parse_args()

    if args.ms is None and args.pickle is not None:
        ds = DynamicSpectraPKL(pickle_file = args.pickle)
    elif args.ms is not None:
        ds = DynamicSpectraMS(ms=args.ms)
        if args.antennas is not None:
            keepants = args.antennas.split(",")
        else:
            keepants = None
        ds.process(ms=args.ms, min_bl=args.min_bl, data_column = args.column, subtract = args.subtract, keepants = keepants, output = args.pickle)
# For now, reread it back in, because Emil's classes need refactoring and I don't have time right now
        ds = DynamicSpectraPKL(pickle_file = args.pickle)
    
    ds.plot_ds(sigma=args.sigma, real_time=True, real_freq=True, outplot=args.outplot)

    if args.dscsv is not None:
        ds.save_ds(csv = args.dscsv)
    if args.dscsv and args.yaml is not None:
        ds.save_yaml(yaml = args.yaml, csv = args.dscsv)
