#! /bin/bash

usage()
{
echo "run_pipeline_task.sh [-d dep] [-t] pipeline task obs_ids
  -d dep     : job number for dependency (afterok)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  pipeline   : the name of the pipeline to run
  task       : the name of the pipeline task to run
  obs_ids     : the obsid to process, or a text file of obsids (newline separated). 
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

shift
task=$1

shift
obs_ids="$@"

# if obsid is empty then just ping help
if [[ -z ${obs_ids} ]]
then
    usage
fi

# set dependency
if [[ ! -z ${dep} ]]
then
    if [[ -f "${obs_ids}" ]]
    then
        depend="--dependency=aftercorr:${dep}"
    else
        depend="--dependency=afterok:${dep}"
    fi
fi

# We want obs_ids to be a comma-separated list in order to be passed to the
# database API as a query parameter.
# First check if obs_ids is a file
if [[ -f "${obs_ids}" ]]; then
    obs_ids="$(echo $(cat ${obs_ids}) | tr ' ' ',')"
else
    obs_ids="$(echo ${obs_ids} | tr ' ' ',')"
fi

# Create an sbatch script
sbatch_script=run_GPM_$(date +'%s').sbatch
curl -s -S -X GET -H "Authorization: Token ${GPMDBTOKEN}" -H "Accept: application/json" "${GPMURL}/processing/api/create_processing_job?pipeline=${pipeline}&task=${task}&hpc=${GPMHPC}&hpc_user=${whoami}&obs_ids=${obs_ids}&sbatch=1" > ${sbatch_script}

sub="sbatch ${depend} --export=ALL ${sbatch_script}"
# Apparently, the --export=ALL in the script header doesn't work the same as the --export=ALL on the cmd line

if [[ ! -z ${tst} ]]
then
    echo "submit via:"
    echo "${sub}"
    exit 0
fi

# submit job
jobid=($(${sub}))
jobid=${jobid[3]}
echo "Submitted ${sbatch_script} as ${jobid}"
