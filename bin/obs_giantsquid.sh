#! /bin/bash

#set -x

time_request="02:00:00"

usage()
{
echo "obs_giantsquid.sh [-p project] [-d depend] [-t] obsid [obsid ...]
  -d depend         : job number for dependency (afterok)
  -p project        : project, (must be specified, no default)
  -t                : test. Don't submit job, just make the batch file
                      and then return the submission command
  -T                : override the default SLURM time request  (${time_request})
  -f                : Force re-download (default is to ignore obsids
                      if the measurement set already exists).
  -o obsid_file     : the path to a file containing obsid(s) to process" 1>&2;
}

#initial variables
pipeuser=${GPMUSER}
depend=
tst=
force=

# parse args and set options
while getopts ':tT:hd:p:o:f' OPTION
do
    case "$OPTION" in
    d)
        depend="--dependency=afterok:${OPTARG}" ;;
    p)
        project=${OPTARG} ;;
    t)
        tst=1 ;;
    T)
        time_request="${OPTARG}" ;;
    f)
        force=1 ;;
    o)
        obsid_file=${OPTARG} ;;
    ? | : | h)
        usage; exit 0 ;;
  esac
done

# If obsid_file is unspecified then exit
if [[ -z $obsid_file ]]
then
    echo "ObsID file (-o) must be supplied"
    usage
    exit 1;
fi

# Read the obsids from a file
obsids="$(cat "$obsid_file" | xargs)"
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
    exit 1;
fi

# Use project in working directory
base="${GPMSCRATCH}/${project}"
mkdir -p "$base"
cd "${base}"

# The logic for the code within the following for-loop is documented
# in a flowchart diagram in doc/images/giantsquid.png

# Task #1: eliminate obsids that have already been downloaded (unless the -f option was given)
if [[ -z $force ]] # i.e. if the -f option was NOT supplied
then
    filtered_obsids=
    for obsid in $obsids
    do
        ms="$obsid/$obsid.ms"
        if [[ ! -d $ms ]] # If the measurement set does NOT exist
        then
            filtered_obsids="$filtered_obsids $obsid"
        else
            echo "Obs ${obsid} already has measurement set on disk. Skipping."
        fi
    done
    obsids="$filtered_obsids"
else
    echo "Force option chosen. DANGER! Existing measurement sets will now be deleted!!"
    for obsid in $obsids
    do
        cd "${base}/${obsid}"
        rm -rf "$obsid.ms"
    done
fi

# Get the list of ASVO jobs
asvo_json=$(singularity exec $GPMCONTAINER giant-squid list ${obsids} --json)

# Tast #2: separate the list into three sublists:
#   1. State = Ready                     -->  Submit download job
#   2. State = Queued or Processing      -->  Currently being processed: do nothing
#   3. All other states, or not in list  -->  Submit preprocessing job

preprocess_obsids=
download_obsids=

for obsid in $obsids
do
    # Get the ASVO job state
    states=($(echo "$asvo_json" | singularity exec $GPMCONTAINER jq -r ".[]| select( .obsid == ${obsid} ).jobState")) # use an array in case there are more than one
    state=${states[0]} # Just grab the first state

    if [[ $state == "Ready" ]]
    then
        echo "Obs ${obsid} ready for download. Adding it to the download list"
        download_obsids="$download_obsids $obsid"
    elif [[ $state == "Processing" || $state == "Queued" ]]
    then
        echo "Obs ${obsid} is already being processed on ASVO. Skipping."
        # Do nothing
    elif [[ $state == "Cancelled" || $state == "Expired" || $state == "Error" ]]
    then
        echo "Obs ${obsid} was previously in state \"${state}\". Will submit fresh preprocessing job for this obs."
        preprocess_obsids="$preprocess_obsids $obsid"
    else
        echo "Obs ${obsid} is not in your ASVO job list. Adding it to the preprocessing list"
        preprocess_obsids="$preprocess_obsids $obsid"
    fi
done

#---------------------------------------
# Submit the giant-squid conversion jobs
#---------------------------------------

if [[ $(echo "$preprocess_obsids" | wc -w) -ge 1 ]]
then

    echo "==================================="
    echo "Preprocessing list: ${preprocess_obsids}"

    if [[ ! -z ${tst} ]]
    then
        echo "Test mode active: Command that would be run is:"
        echo
        echo "singularity exec $GPMCONTAINER giant-squid submit-conv -p avg_time_res=4,avg_freq_res=40,flag_edge_width=80,output=ms $preprocess_obsids"
        echo
    else
        singularity exec $GPMCONTAINER giant-squid submit-conv -p avg_time_res=4,avg_freq_res=40,flag_edge_width=80,output=ms $preprocess_obsids
        echo
        echo "Preprocessing jobs sent to ASVO"
    fi
else
    echo "No preprocessing jobs sent"
fi

#-------------------------------------
# Submit the giant-squid download jobs
#-------------------------------------

if [[ $(echo "$download_obsids" | wc -w) -ge 1 ]]
then

    echo "==================================="
    echo "Download list: ${download_obsids}"

    timestamp=$(date +"%Y%m%d_%H%M%S")

    script="${GPMSCRIPT}/giantsquid_download_${timestamp}.sh"
    cat "${GPMBASE}/templates/giantsquid_download.tmpl" > "${script}"

    chmod 755 "${script}"

    # Construct the sbatch wrapper for the giantsquid script
    sbatch_script="${script%.sh}.sbatch"

    BEGIN="now+1minutes"
    MEM="50G"
    EXPORT="$(echo ${!GPM*} | tr ' ' ','),MWA_ASVO_API_KEY"
    TIME="${time_request}"
    CLUSTERS="${GPMCOPYM}"
    OUTPUT="${GPMLOG}/giantsquid_download_${timestamp}.o%A-%j"
    ERROR="${GPMLOG}/giantsquid_download_${timestamp}.e%A"
    PARTITION="${GPMCOPYQ}"
    ACCOUNT="${GPMACCOUNT}"
    ARRAY="$(echo "$download_obsids" | xargs | tr ' ' ',')" # turn into whitespace-trimmed, comma-separated list

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
#SBATCH --array=1-"$(echo "$download_obsids" | wc -w)"

module load singularity/3.7.4

export SINGULARITY_BINDPATH=${SINGULARITY_BINDPATH}

obsids=\"${download_obsids}\"
obsid=\$(echo \$obsids | cut -d \" \" -f \$SLURM_ARRAY_TASK_ID)

singularity run ${GPMCONTAINER} ${script} \$obsid
    " >> "${sbatch_script}"

    # This is the only task that should reasonably be expected to run on another cluster. 
    # Export all GPM pipeline configurable variables and the MWA_ASVO_API_KEY to ensure 
    # obs_giantsquid completes as expected
    sub="sbatch ${depend} --export="${EXPORT}" ${sbatch_script}"

    if [[ ! -z ${tst} ]]
    then
        echo "script is ${script}"
        echo "submit via:"
        echo "${sub}"
    else

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

    fi
else
    echo "No download jobs sent"
fi

