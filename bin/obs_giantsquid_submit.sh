#! /bin/bash

usage()
{
echo "obs_manta.sh [-p project] [-d depend] [-s timeres] [-k freqres] [-e edgeflag] [-t] obsid [obsid ...]
  -d depend         : job number for dependency (afterok)
  -p project        : project, (must be specified, no default)
  -s timeres        : time resolution in sec. default = 2 s
  -k freqres        : freq resolution in KHz. default = 40 kHz
  -e edgeflag       : number of edge band channels flagged. default = 80
  -t                : test. Don't submit job, just make the batch file
                      and then return the submission command
  -f                : Force re-download (default is to quit with exit code "2"
                      if the measurement set already exists).
  obsid [obsid ...] : the obsid(s) to process" 1>&2;
exit 1;
}

#initial variables
pipeuser=${GPMUSER}
depend=
tst=
timeres=
freqres=
edgeflag=80
force=
obsids=

# parse args and set options
while getopts ':tghd:p:s:k:fe:' OPTION
do
    case "$OPTION" in
    d)
        depend="--dependency=afterok:${OPTARG}" ;;
    p)
        project=${OPTARG} ;;
	s)
	    timeres=${OPTARG} ;;
	k)
	    freqres=${OPTARG} ;;
    t)
        tst=1 ;;
    e)
        edgeflag=${OPTARG} ;;
    f)
        force=1 ;;
    ? | : | h)
        usage ;;
  esac
done

# Set the obsids to be the list of all remaining arguments
shift  "$(($OPTIND -1))"
obsids="$*"
if [[ -z $obsids ]]
then
    echo "No obsids supplied. Nothing to be done."
    exit 0
fi

# If project is not specified then exit
if [[ -z $project ]]
then
    echo "Project (-p) must be supplied"
    usage
fi

# Use project in working directory
base="${GPMSCRATCH}/${project}"
mkdir -p "$base"
cd "${base}"

# Add the metadata to the observations table in the database
# import_observations_from_db.py --obsid "${obslist}"

dllist=""
timestamp=$(date +"%Y%m%d_%H%M%S")
mantacsv="manta_${timestamp}.csv"
>$mantacsv # = Delete contents of the file

# Set up telescope-configuration-dependent options
# Might use these later to get different metafits files etc
for obsid in $obsids
do
    # Note this implicitly 
    if [[ $obsid -lt 1151402936 ]] ; then
        telescope="MWA128T"
        basescale=1.1
        if [[ -z $freqres ]] ; then freqres=40 ; fi
        if [[ -z $timeres ]] ; then timeres=4 ; fi
    elif [[ $obsid -ge 1151402936 ]] && [[ $obsid -lt 1191580576 ]] ; then
        telescope="MWAHEX"
        basescale=2.0
        if [[ -z $freqres ]] ; then freqres=40 ; fi
        if [[ -z $timeres ]] ; then timeres=8 ; fi
    elif [[ $obsid -ge 1191580576 ]] ; then
        telescope="MWALB"
        basescale=0.5
        if [[ -z $freqres ]] ; then freqres=40 ; fi
        if [[ -z $timeres ]] ; then timeres=4 ; fi
    fi

    if [[ -d "${obsid}/${obsid}.ms" && $force -ne 1 ]]
    then
        echo "${obsid}/${obsid}.ms already exists. I will not download it again."
    else
        preprocessor='birli'
        stem="ms"
        dllist=$dllist"$obsid "
    fi
done

# Make sure there is at least one observation to be processed
if [[ ! -s $mantacsv ]]
then
    echo "No observations to download. Exiting..."
    exit
fi

# Construct the manta script to be run
script="${GPMSCRIPT}/manta_${timestamp}.sh"

cat "${GPMBASE}/templates/manta.tmpl" | sed -e "s:CSV:${mantacsv}:g" \
                                 -e "s:STEM:${stem}:g"  \
                                 -e "s:TRES:${timeres}:g" \
                                 -e "s:FRES:${freqres}:g" \
                                 -e "s:OBSIDS:\"${obsids}\":g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

chmod 755 "${script}"

# Construct the sbatch wrapper for the manta script
sbatch_script="${script%.sh}.sbatch"

BEGIN="now+1minutes"
MEM="50G"
EXPORT="$(echo ${!GPM*} | tr ' ' ','),MWA_ASVO_API_KEY"
TIME="00:05:00"
CLUSTERS="${GPMCOPYM}"
OUTPUT="${GPMLOG}/giantsquid_submit_${timestamp}.o%A"
ERROR="${GPMLOG}/giantsquid_submit_${timestamp}.e%A"
PARTITION="${GPMCOPYQ}"
ACCOUNT="${GPMACCOUNT}"

# Override ACCOUNT if GPMCOPYA is not empty
if [[ ! -z $GPMCOPYA ]]
then
    ACCOUNT="--account=${GPMCOPYA}"
fi

echo "#!/bin/bash

#SBATCH --begin=${BEGIN}
#SBATCH --mem=${MEM}
#SBATCH --export=${EXPORT}
#SBATCH --time=${TIME}
#SBATCH --clusters=${CLUSTERS}
#SBATCH --output=${OUTPUT}
#SBATCH --error=${ERROR}
#SBATCH --partition=${PARTITION}
#SBATCH --account=${ACCOUNT}

module load singularity/3.7.4

export SINGULARITY_BINDPATH=${SINGULARITY_BINDPATH}

singularity run ${GPMCONTAINER} ${script}
" >> "${sbatch_script}"

# This is the only task that should reasonably be expected to run on another cluster. 
# Export all GLEAM-X pipeline configurable variables and the MWA_ASVO_API_KEY to ensure 
# obs_manta completes as expected
sub="sbatch ${depend} --export="${EXPORT}" ${sbatch_script}"

if [[ ! -z ${tst} ]]
then
    echo "script is ${script}"
    echo "submit via:"
    echo "${sub}"
    exit 0
fi

# submit job
jobid=($(${sub}))
jobid=${jobid[3]}

# rename the err/output files as we now know the jobid
error="${error//%A/${jobid[0]}}"
output="${output//%A/${jobid[0]}}"

# record submission
n=1
for obsid in $dllist
do
    if [ "${GPMTRACK}" = "track" ]
    then
        ${GPMCONTAINER} track_task.py queue --jobid="${jobid[0]}" --taskid="${n}" --task='download' --submission_time="$(date +%s)" \
                        --batch_file="${script}" --obs_id="${obsid}" --stderr="${error}" --stdout="${output}"
    fi
    ((n+=1))
done

echo "Submitted ${script} as ${jobid} . Follow progress here:"
echo "${output}"
echo "${error}"
