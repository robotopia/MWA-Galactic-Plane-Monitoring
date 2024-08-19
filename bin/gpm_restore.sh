#!/bin/bash

usage()
{
echo "obs_restore.sh [-d dep] [-t] obsnum
  Restores the given observation(s) from its backup location (Acacia) to disk.
  It both downloads and extracts the backed-up tar file.

  -d dep : job number for dependency (afterok)
  -t     : test. Don't submit job, just make the batch file
           and then return the submission command

  obsnum : the obsid to be restored, or a text file of obsids (newline separated).
         A job-array task will be submitted to process the collection of obsids. " 1>&2;
}

#initial variables
dep=
tst=

# parse args and set options
while getopts ':tzd:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG}
        ;;
    z)
        debug=1
        ;;
    t)
        tst=1
        ;;
    h)
        usage
	exit 0
        ;;
    ? | :)
        usage
	exit 1
        ;;
  esac
done
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsnum=$1

if [[ -z $obsnum ]]
then
  usage
  exit 1
fi

if [[ ! -z ${dep} ]]
then
    if [[ -f ${obsnum} ]]
    then
        depend="--dependency=aftercorr:${dep}"
    else
        depend="--dependency=afterok:${dep}"
    fi
fi

output="${GPMLOG}/restore_${obsnum}.o%A"
error="${GPMLOG}/restore_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

sbatch_script="${GPMSCRIPT}/restore_${obsnum}.sbatch"

echo "#!/bin/bash

# GPM Version: ${GPMGITVERSION}

#SBATCH --export=ALL
#SBATCH --time=00:20:00
#SBATCH --mem=150M
#SBATCH --clusters=${GPMCOMPUTER}
#SBATCH --output=${output}
#SBATCH --error=${error}
#SBATCH --account=${GPMACCOUNT}
#SBATCH --partition=${GPMCOPYQ}" > ${sbatch_script}

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l "${obsnum}" | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
    if [ ! -z ${GPMMAXARRAYJOBS} ]
    then
        jobarray="${jobarray}%${GPMMAXARRAYJOBS}"
    fi
    echo "#SBATCH ${jobarray}

# Get obsid for this array job
obsnum=\$(sed -n -e \"\${SLURM_ARRAY_TASK_ID}\"p \"${obsnum}\")

taskid=\"\${SLURM_ARRAY_TASK_ID}\"
jobid=\"\${SLURM_ARRAY_JOB_ID}\"
" >> ${sbatch_script}
else
    echo "
obsnum=${obsnum}

taskid=1
jobid=\"\${SLURM_JOB_ID}\"
" >> ${sbatch_script}
fi

# Define the test_fail function in the script
echo "
function test_fail {
if [[ \$1 != 0 ]]
then
    track_task.py fail --jobid=\"\${jobid}\" --taskid=\"\${taskid}\" --finish_time=\"\$(date +%s)\"
    exit \"\$1\"
fi
}
" >> ${sbatch_script}

echo "
# Load the rclone and singularity modules
module load $(module -t --default -r avail "^rclone$" 2>&1 | grep -v ':' | head -1)
module load $(module -t --default -r avail "^singularity$" 2>&1 | grep -v ':' | head -1)
" >> ${sbatch_script}

# Declare the job 'started'
echo "# Update database
singularity exec $GPMCONTAINER track_task.py start --jobid=\"\${jobid}\" --taskid=\"\${taskid}\" --start_time=\"\$(date +%s)\"
" >> ${sbatch_script}

# Add the main task: download it via rclone!
echo "
# Load environment settings afresh -- IGNORE THIS FOR NOW (slated for a future version)
#hpc_user_settings=\$(singularity exec $GPMCONTAINER $GPMBASE/gpm_track.py get_environment)

acacia_path_info=\$(singularity exec $GPMCONTAINER $GPMBASE/gpm_track.py acacia_path --obs_file \$obsnum)

read -r obsid epoch tar_contains_folder acacia_path <<< \"\$acacia_path_info\"

if [[ \"\$tar_contains_folder\" == \"0\" ]]
then
  SCRATCH_PATH=$GPMSCRATCH/\$epoch/\$obsid
else
  SCRATCH_PATH=$GPMSCRATCH/\$epoch
fi
echo "-----------------------------"
echo "Downloading \$obsid to $GPMSCRATCH/\$epoch/\$obsid"
mkdir -p \$SCRATCH_PATH
cd \$SCRATCH_PATH
rclone cat \$acacia_path | tar xvzmf -
" >> ${sbatch_script}

# Declare the job finished
echo "# Update database with finished!
singularity exec $GPMCONTAINER track_task.py finish --jobid=\"\${jobid}\" --taskid=\"\${taskid}\" --finish_time=\"\$(date +%s)\"
" >> ${sbatch_script}

# Submit the job
sub="sbatch ${depend} --export=ALL ${sbatch_script}"

if [[ ! -z ${tst} ]]
then
    echo -e "script is:\n\t${sbatch_script}"
    echo -e "submit via:\n\t${sub}"
    exit 0
fi

# submit job
jobid=($(${sub}))
jobid=${jobid[3]}

echo "Submitted ${script} as ${jobid} . Follow progress here:"

# Add rows to the database 'processing' table that will track the progress of this submission
${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_jobs --jobid="${jobid}" --task='restore' --batch_file="${script}" --obs_file="${obsnum}" --stderr="${error}" --stdout="${output}"
${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue_jobs --jobid="${jobid}" --submission_time="$(date +%s)"

echo "STDOUTs: ${output}"
echo "STDERRs: ${error}"
