#!/bin/bash -l
#SBATCH --account=mwasci
#SBATCH --partition=workq
#SBATCH --time=00:05:00
#SBATCH --nodes=1

# The regular monitoring script that runs every hour to see if a new calibrator has been observed

epoch=$(determine_epoch.py)
# TODO: make a directory based on the epoch and go there to do everything
# TODO: Somehow make the errors and outputs of this script go to that directory!!

obsid=$(gp_monitor_lookup.py --cal)

if [[ $obsid != ""]]
then
    dep=($(obs_manta.sh -p $epoch -o $obsid))
    depend=${dep[3]}
    dep=($(obs_autoflag.sh -d ${depend} -p ${epoch} $obsnum))
    depend=${dep[3]}
    dep=($(obs_autocal.sh -d ${depend} -p ${epoch} $obsnum))
fi
