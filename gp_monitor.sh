#!/bin/bash -l
#SBATCH --account=mwasci
#SBATCH --partition=workq
#SBATCH --time=00:05:00
#SBATCH --nodes=1

# Manual setup: user must add their own output and error log destinations
# Otherwise they will go to /home/$USER 

# We might need to source to GLEAM-X and the GPM profiles here if this is
# a script kicked off from the slurm cron job. Not sure if bash profiles
# would be executed by the slurm magic. These are to ensure the 
# environment in the slurm cron job is set up correctly. 
GXPROFILE=
GPMPROFILE=


for var in GXPROFILE GPMPROFILE 
do
    if [[ -f "${!var}" ]]
    then 
        source "${!var}"
    else 
        echo "Unable to locate the ${var} profile. "
        echo "${var} currently set to ${!var} "
        return 1 
    fi
done

# Manual setup
datadir="${GXSCRATCH}"

# Common singularity command to run the python code
SINGCMD="singularity exec ${GXCONTAINER} "

obsid=$(${SINGCMD} "${GPMBASE}/gp_monitor_lookup.py" --cal)

if [[ $obsid != "" ]]
then
    epoch=$(${SINGCMD} "${GPMBASE}/determine_epoch.py" --obsid $obsid)

    # Note: output format is: Epoch%03d
    pdir="$datadir/$epoch"

    if [[ ! -d "${pdir}" ]]
    then
        mkdir "${pdir}"
    fi

    # TODO: Here we need to add an entry to the database to say that we are looking at this observation
    STATUS=$(${SINGCMD} "${GPMBASE}/gpm_track.py" check_obs_status --obs_id "$obsid")
    
    if [[ "${STATUS}" == "unprocessed" ]]
    then
        dep=($(obs_manta.sh -p "${epoch}" -o "${obsid}"))
        depend=${dep[3]}
        dep=($(obs_autoflag.sh -d ${depend} -p "${epoch}" "${obsid}"))
        depend=${dep[3]}
        dep=($(obs_autocal.sh -d ${depend} -p "${epoch}" "${obsid}"))
        depend=${dep[3]}
        obs_gpmonim.sh -d ${depend} -p "${epoch}" "${obsid}"
    
    elif [[ "${STATUS}" == "checking" ]]
    then 
        echo "Placeholder. ${obsid} might be processed already?"
    fi
fi
