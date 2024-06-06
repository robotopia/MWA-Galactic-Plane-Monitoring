#!/bin/bash

set -x

obsid="$1"

# Get the associated calibration observation
calid=$(${GPMBASE}/gpm_track.py obs_calibrator --obs_id "$obsid")
if [[ -z "$calid" ]]
then
    echo "No calibrator found for obsid $obsid"
    exit 1
fi

# Move to the data directory of the calibrator
epoch=$(${GPMBASE}/gpm_track.py obs_epoch --obs_id $calid)
caldir="${GPMSCRATCH}/${epoch}/${calid}"
mkdir -p "$caldir"
cd "${caldir}"

# Find the calibration file's name from the dabtabase
calfile=${calid}_local_gleam_model_solutions_initial_ref.bin

# If it STILL doesn't exist, insist to the user that it should
if [[ ! -f "$calfile" ]]
then
    echo "Could not find calibration solution \"$calfile\""
    echo "Please make it available."
    exit 1
fi

# Need to confirm the python script works
#result=$(${GPMBASE}/check_solutions.py -t 0.5 -s 4 "${calfile}")
#if echo "${result}" | grep -q fail
#then
#    mv "${calfile}" "${calfile%.bin}_failed.bin"
#    echo "Calibration solutions file failed checks. Exiting. "
#    exit 1
#fi

# Return (by echoing) the full path to the calibration file
echo $caldir/$calfile
