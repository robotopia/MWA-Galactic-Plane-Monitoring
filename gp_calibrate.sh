# This script is to be run inside the GPM container (which can be the GLEAM-X container)
# usage: ./gp_calibrate.sh <cal_id>

calid="$1"

# Manual setup
datadir="${GPMSCRATCH}"

# Common singularity command to run the python code
SINGCMD="singularity exec ${GPMCONTAINER} "

if [[ $calid != "" ]]
then
    epoch=Epoch$(${SINGCMD} "${GPMBASE}/determine_epoch.py" --calid $calid)

    # Note: output format is: Epoch%03d
    pdir="$datadir/$epoch"

    if [[ ! -d "${pdir}" ]]
    then
        mkdir "${pdir}"
    fi

    ${SINGCMD} "${GPMBASE}/gpm_track.py" import_obs --obs_id "$calid"
    
    echo "${calid}" > "${pdir}/calid.txt"

    dep=($(obs_manta.sh -p "${epoch}" -o "${pdir}/calid.txt"))
    depend=${dep[3]}
    dep=($(obs_autoflag.sh -d ${depend} -p "${epoch}" "${calid}"))
    depend=${dep[3]}
    dep=($(obs_autocal.sh -d ${depend} -p "${epoch}" -f 0.5 "${calid}"))
    depend=${dep[3]}
    #obs_gpmonim.sh -d ${depend} -p "${epoch}" "${obsid}"

fi
