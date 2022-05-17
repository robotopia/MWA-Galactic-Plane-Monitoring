#!/bin/bash -l
#SBATCH --account=mwasci
#SBATCH --partition=workq
#SBATCH --time=00:05:00
#SBATCH --nodes=1

# TODO: set up some environment variables so that the errors and outputs go to a sensible directory
# Otherwise they will go to /home/$USER 

# The regular monitoring script that runs every hour to see if a new calibrator has been observed

obsid=$(gp_monitor_lookup.py --cal)

if [[ $obsid != ""]]
then
    epoch=$(determine_epoch.py --obsid $obsid)
# Note: output format is: Epoch%03d
# TODO: first part of directory stem should probably be set from template or environment variables
    pdir=/astro/mwasci/$USER/$epoch
    if [[ ! -d $pdir ]]
    then
        mkdir $pdir
    fi
    dep=($(obs_manta.sh -p $epoch -o $obsid))
    depend=${dep[3]}
    dep=($(obs_autoflag.sh -d ${depend} -p ${epoch} $obsnum))
    depend=${dep[3]}
    dep=($(obs_autocal.sh -d ${depend} -p ${epoch} $obsnum))
    depend=${dep[3]}
# TODO: template obs_gp_image.sh based on existing skeleton gp_image.sh
# TODO: run obs_gp_image.sh with the new created dependency, -c $obsid -d $depend
fi
