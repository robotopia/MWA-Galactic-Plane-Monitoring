#! /bin/bash

usage()
{
echo "run_pipeline_step.sh [-d dep] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  pipeline   : the name of the pipeline to run
  step       : the name of the pipeline step to run
  hpc        : the name of the HPC system this is running on
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

dep=
tst=

# parse args and set options
while getopts ':td:a:p:' OPTION
do
    case "$OPTION" in
	d)
	    dep=${OPTARG}
	    ;;
	t)
	    tst=1
	    ;;
	? | : | h)
	    usage
	    ;;
  esac
done
# Consume the remaining arguments
shift  "$(($OPTIND -1))"
pipeline=$1

shift  "$(($OPTIND -1))"
step=$1

shift  "$(($OPTIND -1))"
hpc=$1

shift  "$(($OPTIND -1))"
obsnum=$1

# if obsid is empty then just ping help
if [[ -z ${obsnum} ]]
then
    usage
fi

# Get job enviroment
exports="$(curl -X GET -H "Authorization: Token ${GPMDBTOKEN}" -H "Accept: application/json" "https://gpm.mwa-image-plane.cloud.edu.au/processing/api/load_job_environment?pipeline=${pipeline}&task=${step}&hpc=${hpc}&hpc_user=${whoami}")"
echo "${exports}"
eval "${exports}"

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l "${obsnum}" | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
else
    numfiles=1
    jobarray=''
fi

# set dependency
if [[ ! -z ${dep} ]]
then
    if [[ -f ${obsnum} ]]
    then
        depend="--dependency=aftercorr:${dep}"
    else
        depend="--dependency=afterok:${dep}"
    fi
fi

script="${GPMSCRIPT}/${GPMOBSSCRIPT}_${obsnum}.sh"

cat "${GPMBASE}/templates/${GPMOBSSCRIPT}.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" > "${script}"


output="${GPMLOG}/${GPMOBSSCRIPT}_${obsnum}.o%A"
error="${GPMLOG}/${GPMOBSSCRIPT}_${obsnum}.e%A"
if [[ -f ${obsnum} ]]
then
    output="${output}_%a"
    error="${error}_%a"
fi

chmod 755 "${script}"

###############################
# Construct the sbatch script #
###############################

sbatch_script="${script%.sh}.sbatch"
echo '#!/bin/bash' > ${sbatch_script}
echo >> ${sbatch_script}

# Get the pipeline git version number, for the record
gitversion=$(git --git-dir=${GPMBASE}/.git describe --tags --long)
echo "# GPM version: ${gitversion}" >> ${sbatch_script}
echo >> ${sbatch_script}

# Construct the SBATCH header
echo "#SBATCH --export=ALL" >> ${sbatch_script}
if [ ! -z $GPMACCOUNT ];       then echo "#SBATCH --account=${GPMACCOUNT}"               >> ${sbatch_script}; fi
if [ ! -z $GPMSTANDARDQ ];     then echo "#SBATCH --partition=${GPMSTANDARDQ}"           >> ${sbatch_script}; fi
if [ ! -z $GPMTIME ];          then echo "#SBATCH --time=${GPMTIME}"                     >> ${sbatch_script}; fi
if [ ! -z $GPMABSMEMORY ];     then echo "#SBATCH --mem=${GPMABSMEMORY}"                 >> ${sbatch_script}; fi
if [ ! -z $GPMCLUSTER ];       then echo "#SBATCH --clusters=${GPMCLUSTER}"              >> ${sbatch_script}; fi
if [ ! -z $GPMNPCPUS ];        then echo "#SBATCH --cpus-per-task=${GPMNPCPUS}"          >> ${sbatch_script}; fi
if [ ! -z $GPMNTASKSPERNODE ]; then echo "#SBATCH --ntasks-per-node=${GPMNTASKSPERNODE}" >> ${sbatch_script}; fi
echo "#SBATCH --output=${output}" >> ${sbatch_script}
echo "#SBATCH --error=${error}" >> ${sbatch_script}
if [ ! -z $jobarray ];         then echo "#SBATCH ${jobarray}"                           >> ${sbatch_script}; fi

echo >> ${sbatch_script}
echo "${exports}" >> ${sbatch_script}

echo >> ${sbatch_script}
echo "module load $(module -t --default -r avail "^singularity$" 2>&1 | grep -v ':' | head -1)">> ${sbatch_script}

echo "singularity run ${GPMCONTAINER} ${script}" >> ${sbatch_script}

sub="sbatch ${depend} --export=ALL ${sbatch_script}"
# Apparently, the --export=ALL in the script header doesn't work the same as the --export=ALL on the cmd line

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
echo "Submitted ${script} as ${jobid} Follow progress here:"

# Add rows to the database 'processing' table that will track the progress of this submission
${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_jobs --jobid="${jobid}" --task='flag' --batch_file="${script}" --obs_file="${obsnum}" --stderr="${error}" --stdout="${output}"
${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue_jobs --jobid="${jobid}" --submission_time="$(date +%s)"

echo "STDOUTs: ${output}"
echo "STDERRs: ${error}"

