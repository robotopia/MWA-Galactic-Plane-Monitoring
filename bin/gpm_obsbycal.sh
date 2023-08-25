#! /bin/bash

usage()
{
echo "gpm_obsbycal.sh [-t] calid
  calid     : the obsid of the calibrator, the assigned observations for which will be processed." 1>&2;
exit 1;
}

pipeuser="${GPMUSER}"

#initial variables
tst=
# parse args and set options
while getopts ':tzd:a:p:' OPTION
do
    case "$OPTION" in
	? | : | h)
	    usage
	    ;;
  esac
done
# set the calid to be the first non option
shift  "$(($OPTIND -1))"
calid=$1

queue="-p ${GPMSTANDARDQ}"

# if obsid is empty then just print help

if [[ -z ${calid} ]]
then
    usage
fi

# Common singularity command to run the python code
SINGCMD="singularity exec ${GPMCONTAINER} "

# Move to the data directory of the calibrator
epoch=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_epoch --obsid $calid)
caldir="${GPMSCRATCH}/${epoch}/${calid}"
mkdir -p "$caldir"
cd "${caldir}"

# Find the calibration file's name from the dabtabase
cal_acacia_path=$(${SINGCMD} "${GPMBASE}/gpm_track.py" acacia_path --obs_id $calid --value "calibration solution")
if [[ -z "$cal_acacia_path" ]]
then
    echo "Calibration solution filename has not been entered into the GPM database for calid $calid"
    exit 1
fi

calfile=$(basename "$cal_acacia_path")

# If it doesn't already exist locally, try to download it from acacia
if [[ ! -f "$calfile" ]]
then
    echo "No local copy of calibration solution found. Attempting to download calibration solution from Acacia ($cal_acacia_path)..."
    mc cp "$cal_acacia_path" "$calfile"
fi

# If it STILL doesn't exist, insist to the user that it should
if [[ ! -f "$calfile" ]]
then
    echo "Could not find calibration solution \"$calfile\" either locally ($caldir) or on Acacia ($calfile)"
    echo "Please make it available."
    exit 1
fi

# Need to confirm the python script works
result=$(${SINGCMD} "${GPMBASE}/check_solutions.py" -t 0.5 -s 4 "${calfile}")
if echo "${result}" | grep -q fail
then
    mv "${calfile}" "${calfile%.bin}_failed.bin"
    echo "Calibration solutions file failed checks. Exiting. "

    # Email goes here

    exit 1
fi

# Status-based pipeline. Deprecated.
#${SINGCMD} "${GPMBASE}/gpm_track.py" obs_status --obs_id ${calid} --status "calibrated"
#obsids=$(${SINGCMD} "${GPMBASE}/gp_monitor_lookup.py" --calid $calid --allowed-status unprocessed)

# Find all the observations who have been assigned the given calibrator
obsids=$(${SINGCMD} ${GPMBASE}/gpm_track.py ls_obs_for_cal --calid $calid)

if [[ $obsids != "" ]]
then
    for obs in $obsids
    do

        epoch=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_epoch --obsid $obs)
        datadir="${GPMSCRATCH}/${epoch}/${obs}"
        mkdir -p $datadir
        cd $datadir

        echo "${obs}" > "${obs}_obsid.txt"

        dep=($(obs_manta.sh -p $epoch -o "${obs}_obsid.txt"))
        depend=${dep[3]}
        dep=($(obs_autoflag.sh -d ${depend} -p ${epoch} $obs))
        depend=${dep[3]}
        dep=($(obs_apply_cal.sh -d ${depend} -p "${epoch}" -c $calfile -z  $obs))
        depend=${dep[3]}
        dep=($(obs_uvflag.sh -d ${depend} -p "${epoch}" -z $obs))
        depend=${dep[3]}
        dep=($(obs_image.sh -d ${depend} -p "${epoch}" -z $obs))
        depend=${dep[3]}
        dep=($(obs_transient.sh -d ${depend} -p "${epoch}" -z $obs))
        depend=${dep[3]}
        depp=($(obs_postimage.sh -d ${depend} -p "${epoch}" -P I $obs))
        deppp=($(obs_postimage.sh -d ${depend} -p "${epoch}" -P V $obs))
        dep=($(obs_tfilter.sh -d ${depend} -p "${epoch}" $obs))
    done

else
    echo "No obsids have been assigned to calibration $calid in the database"
fi
