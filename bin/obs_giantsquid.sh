#! /bin/bash

usage()
{
echo "obs_giantsquid_download.sh [-p project] [-d depend] [-t] obsid [obsid ...]
  -d depend         : job number for dependency (afterok)
  -p project        : project, (must be specified, no default)
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
    t)
        tst=1 ;;
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

timestamp=$(date +"%Y%m%d_%H%M%S")

# The logic for the code within the following for-loop is documented
# in a flowchart diagram in doc/images/giantsquid.png
preprocess_list=
download_list=

for obsid in $obsids
do
    # Already downloaded? (= Yes, if the measurement set folder exists)
    ms="$obsid/$obsid.ms"
    if [[ -d $ms ]]
    then
        # Measurement set exists. Force re-download?
        if [[ -z $force ]] # i.e. if re-download NOT forced
        then
            # Do nothing for this obsid
            echo "Observation ${obsid} has already been downloaded. Skipping..."
            continue
        fi

        # Does ASVO job exist?
    fi
done

# Construct the giant-squid script to be run
script="${GPMSCRIPT}/giantsquid_${timestamp}.sh"

cat "${GPMBASE}/templates/giantsquid_download.tmpl" | sed \
                                 -e "s:OBSIDS:\"${obsids}\":g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

chmod 755 "${script}"

# Construct the sbatch wrapper for the giantsquid script
sbatch_script="${script%.sh}.sbatch"

BEGIN="now+1minutes"
MEM="50G"
EXPORT="$(echo ${!GPM*} | tr ' ' ','),MWA_ASVO_API_KEY"
TIME="01:30:00"
CLUSTERS="${GPMCOPYM}"
OUTPUT="${GPMLOG}/giantsquid_download_${timestamp}.o%A"
ERROR="${GPMLOG}/giantsquid_download_${timestamp}.e%A"
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
# obs_giantsquid completes as expected
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
for obsid in $obsids
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
