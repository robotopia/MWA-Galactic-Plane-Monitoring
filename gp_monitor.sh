#!/bin/bash -l
#SBATCH --account=mwasci
#SBATCH --partition=workq
#SBATCH --time=00:05:00
#SBATCH --nodes=1

# Manual setup: user must add their own output and error log destinations
# Otherwise they will go to /home/$USER 

# Manual setup:
export PYTHONPATH=$PYTHONPATH:/astro/mwasci/$USER/MWA-Galactic-Plane-Monitoring

# Manual setup
datadir=/astro/mwasci

# The regular monitoring script that runs every hour to see if a new calibrator has been observed

# TODO: Check that the logging goes to STDERR and doesn't go to STDOUT and get assigned as a variable
obsid=$(gp_monitor_lookup.py --cal)

if [[ $obsid != ""]]
then
    epoch=$(determine_epoch.py --obsid $obsid)
# Note: output format is: Epoch%03d
    pdir=$datadir/$USER/$epoch
    if [[ ! -d $pdir ]]
    then
        mkdir $pdir
    fi
# TODO: Here we need to add an entry to the database to say that we are looking at this observation
    dep=($(obs_manta.sh -p $epoch -o $obsid))
    depend=${dep[3]}
    dep=($(obs_autoflag.sh -d ${depend} -p ${epoch} $obsnum))
    depend=${dep[3]}
    dep=($(obs_autocal.sh -d ${depend} -p ${epoch} $obsnum))
    depend=${dep[3]}
    obs_gpmonim.sh -d ${depend} -p ${epoch} ${obsnum}
fi
