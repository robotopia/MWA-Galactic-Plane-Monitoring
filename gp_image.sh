#!/bin/bash -l
#SBATCH --account=mwasci
#SBATCH --partition=workq
#SBATCH --time=00:05:00
#SBATCH --nodes=1

# The gp_imaging script that, if the calibration is successful, runs on the rest of the data
# It retries every hour to do any observation that hasn't yet been entered into our processing database
# When every observation has been processed it no longer submits itself to the queue

epoch=$(determine_epoch.py --obsid $CALID)
epoch="Epoch"$epoch
# TODO: define with environment variables
pdir=/astro/mwasci/$USER/$epoch
cd $pdir

# TODO: Insert test of calibration quality here. Only if the calibrator is good enough, proceed to the next step



# This does somewhat rely on the calibrator downloading and processing correctly within 24h
# TODO: change this code so that you can give it a --pincal option
obsid=$(gp_monitor_lookup.py --pincal $CALID)

if [[ $obsid != ""]]
then
    for obs in $obsid
    do
        dep=($(obs_manta.sh -p $epoch -o $obsid))
        depend=${dep[3]}
        dep=($(obs_autoflag.sh -d ${depend} -p ${epoch} $obsnum))
        depend=${dep[3]}
        dep=($(obs_apply_cal.sh -d ${depend} -p "${epoch}" -c $CALID -z  $obsnum))
        depend=${dep[3]}
        dep=($(obs_uvflag.sh -d ${depend} -p "${epoch}" -z $obsnum))
        depend=${dep[3]}
        dep=($(obs_image.sh -d ${depend} -p "${epoch}" -z $obsnum))
        depend=${dep[3]}
        dep=($(obs_transient.sh -d ${depend} -p "${epoch}" -z $obsnum))
    done
fi

# TODO the else statement for the calibration quality -- email the user to say that their calibration didn't work
