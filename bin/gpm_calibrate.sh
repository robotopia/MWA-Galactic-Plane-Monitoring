# usage: ./gpm_calibrate.sh <cal_id>

calid="$1"

# Manual setup
datadir="${GPMSCRATCH}"

# Common singularity command to run the python code
SINGCMD="singularity exec ${GPMCONTAINER} "

if [[ $calid != "" ]]
then
    epoch=Epoch$(${SINGCMD} "${GPMBASE}/determine_epoch.py" --obsid $calid)

    pdir="$datadir/$epoch"
    mkdir -p "${pdir}"

    ${SINGCMD} "${GPMBASE}/gpm_track.py" import_obs --obs_id "$calid"
    
    echo "${calid}" > "${pdir}/calid.txt"

    dep=($(obs_manta.sh -p "${epoch}" -o "${pdir}/calid.txt"))
    depend=${dep[3]}
    dep=($(obs_autoflag.sh -d ${depend} -p "${epoch}" "${calid}"))
    depend=${dep[3]}
    dep=($(obs_autocal.sh -d ${depend} -p "${epoch}" -F 0.5 "${calid}"))
    depend=${dep[3]}

fi
