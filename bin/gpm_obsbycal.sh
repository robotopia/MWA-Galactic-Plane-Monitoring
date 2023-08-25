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
while getopts ':t' OPTION
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
epoch=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_epoch --obs_id $calid)
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
obsids=$(${SINGCMD} ${GPMBASE}/gpm_track.py ls_obs_for_cal --cal_id $calid)

if [[ $obsids != "" ]]
then
    for obs in $obsids
    do

        # Start with no dependency
        depend=
        epoch=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_epoch --obs_id $obs)
        datadir="${GPMSCRATCH}/${epoch}"
        mkdir -p $datadir
        cd $datadir

        echo "Running manta:"
        echo "${obs}" > "${obs}_obsid.txt"

        dep=($(obs_manta.sh ${depend} -p $epoch -o "${obs}_obsid.txt"))
        case "$?" in
            0)
                depend="-d ${dep[3]}"
                ;;
            1)
                echo "obs_manta.sh failed. Stopping gpm_obsbycal.sh for ${obs}"
                continue
                ;;
            2)
                depend=""
                ;;
        esac
        echo "ObsID $obs (manta): ${dep[*]}"

        cmd="obs_autoflag.sh ${depend} -p ${epoch} $obs"
        echo "Running autoflag: $cmd"

        dep=($(${cmd}))
        echo "ObsID $obs (autoflag): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_apply_cal.sh ${depend} -p "${epoch}" -c "$caldir/$calfile" -z  $obs))
        echo "ObsID $obs (apply_cal): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_uvflag.sh ${depend} -p "${epoch}" -z $obs))
        echo "ObsID $obs (uvflag): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_image.sh ${depend} -p "${epoch}" -z $obs))
        echo "ObsID $obs (image): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_transient.sh ${depend} -p "${epoch}" -z $obs))
        echo "ObsID $obs (transient): ${dep[*]}"
        depend="-d ${dep[3]}"
        depp=($(obs_postimage.sh ${depend} -p "${epoch}" -P I $obs))
        echo "ObsID $obs (postimage-I): ${depp[*]}"
        deppp=($(obs_postimage.sh ${depend} -p "${epoch}" -P V $obs))
        echo "ObsID $obs (postimage-V): ${deppp[*]}"
        dep=($(obs_tfilter.sh ${depend} -p "${epoch}" $obs))
        echo "ObsID $obs (tfilter): ${dep[*]}"
    done

else
    echo "No obsids have been assigned to calibration $calid in the database"
fi
