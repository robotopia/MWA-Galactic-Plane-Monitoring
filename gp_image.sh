#!/bin/bash -l
#SBATCH --account=mwasci
#SBATCH --partition=workq
#SBATCH --time=00:05:00
#SBATCH --nodes=1

# TODO: How do I easily make sure every python script runs in the singularity container
# without prefixing everything with singularity exec ....
# TJG: We could try a sneaky ./${GPMBASE}/script_name.py trick. 
#      Not sure how this will work with other imported python scripts from this repo
#      Might need to install in user space and map to it with pip install. Will play. 

# The gp_imaging script that, if the calibration is successful, runs on the rest of the data
# It retries every hour to do any observation that hasn't yet been entered into our processing database
# When every observation has been processed it no longer submits itself to the queue

EPOCH=$(determine_epoch.py --obsid $CALID)
EPOCH="Epoch${EPOCH}"

# TODO: define with environment variables
DATADIR="${GPMSCRATCH}/${EPOCH}"
cd "${DATADIR}" || exit 1

# Test to see if the calibration solution meets minimum quality control. At the moment
# this is a simple check based on the number of flagged solutions
SOLUTIONS="${CALID}/${CALID}solutions_initial_ref.bin"

# Need to confirm the python script works
result=$(check_solutions.py -t 0.25 check "${SOLUTIONS}")
if echo "${result}" | grep -q fail
then
    mv "${SOLUTIONS}" "${SOLUTIONS%.bin}_ref_failed.bin"
    echo "Calibration solutions file failed checks. Exiting. "

    # Email goes here

    exit 111
fi

# Find all the observations taken within +/-12h of that calibrator
obsid=$(gp_monitor_lookup.py --calid $CALID)

if [[ $obsid != "" ]]
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
