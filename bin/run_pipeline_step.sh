#! /bin/bash

usage()
{
echo "run_pipeline_task.sh [-d dep] [-t] pipeline tasks [obs_id [obs_id [...]]]
  -d dep     : Job number for dependency
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  -z         : Debug mode, so adjusts the CORRECTED_DATA column
  pipeline   : the name of the pipeline to run
  tasks      : the name of the pipeline task to run, as a whitespace-separated,
               *quoted* listed, e.g. \"download flag calibrate\"
  obs_id     : can be:
                 1. actual obs_ids (e.g. 1234567890),
                 2. epochs (e.g. Epoch1000), in which case it represents all observations from that epoch,
                 3. a single text file containing obs_ids (newline separated).
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

dep=
tst=
debug=0

# parse args and set options
while getopts ':td:a:p:z' OPTION
do
    case "$OPTION" in
    d) dep=${OPTARG} ;;
    t) tst=1 ;;
    z) debug=1 ;;
    ? | : | h) usage ;;
  esac
done

# Consume the remaining arguments
shift  "$(($OPTIND -1))"
pipeline=$1

shift
tasks=($1)

shift
obs_ids="$@"

# if obsid is empty then just ping help
if [[ -z ${obs_ids} ]]
then
    usage
fi

# We want obs_ids to be a comma-separated list in order to be passed to the
# database API as a query parameter.
# First check if obs_ids is a file
if [[ -f "${obs_ids}" ]]; then
    obs_ids="$(echo $(cat ${obs_ids}) | tr ' ' ',')"
else
    obs_ids="$(echo ${obs_ids} | tr ' ' ',')"
fi

for task in "${tasks[@]}"; do

  # Set dependency
  if [[ ! -z ${dep} ]]; then
    depend="--dependency=aftercorr:${dep}"
  else
    depend=
  fi

  # Create an sbatch script
  sbatch_script=run_GPM_$(date +'%s').sbatch
  curl -s -S -G -X GET \
    -H "Authorization: Token ${GPMDBTOKEN}" \
    -H "Accept: application/json" \
    --data-urlencode "pipeline=${pipeline}" \
    --data-urlencode "task=${task}" \
    --data-urlencode "hpc=${GPMHPC}" \
    --data-urlencode "hpc_user=${whoami}" \
    --data-urlencode "obs_ids=${obs_ids}" \
    --data-urlencode "sbatch=1" \
    --data-urlencode "debug_mode=${debug}" \
    -o "${sbatch_script}" \
    "${GPMURL}/processing/api/create_processing_job"

  if [ $? -eq 22 ]; then
    echo "Could not retrieve sbatch script from ${GPMURL}/processing/api/create_processing_job using:"
    echo "\tpipeline=${pipeline}"
    echo "\ttask=${task}"
    echo "\thpc=${GPMHPC}"
    echo "\thpc_user=${whoami}"
    echo "\tobs_ids=${obs_ids}"
    echo "\tsbatch=1"
    echo "\tdebug_mode=${debug}"
    echo "\tGPMDBTOKEN=\${GPMDBTOKEN}"
    exit 1
  fi

  # Create a batch script that the sbatch script will call
  script=${sbatch_script%.sbatch}.sh
  curl -f -s -S -G -X GET \
    -H "Authorization: Token ${GPMDBTOKEN}" \
    -H "Accept: application/json" \
    --data-urlencode "task=${task}" \
    -o "${script}" \
    "${GPMURL}/processing/api/get_template"

  if [ $? -eq 22 ]; then
    echo "Could not retrieve template from ${GPMURL}/processing/api/get_template using:"
    echo "\ttask=${task}"
    echo "\tGPMDBTOKEN=\${GPMDBTOKEN}"
    exit 1
  fi

  chmod +x "${script}"

  # Construct the line for submitting the sbatch script to the queue
  sub="sbatch ${depend} --export=SCRIPT_PATH=$(realpath "${sbatch_script}") ${sbatch_script}"

  # If user requested "test" mode, then only display this line and exit
  if [[ ! -z ${tst} ]]
  then
      echo "submit via:"
      echo "${sub}"
      exit 0
  fi

  # Submit job!
  job_id=($(${sub}))
  if [[ $? -ne 0 ]]; then
      echo "Submission of ${sbatch_script} FAILED"
      exit 1
  fi

  # Hacky parsing of the SLURM JobID from the stdout of the sbatch call
  job_id=${job_id[3]}
  echo "Submitted ${sbatch_script} as ${job_id}"

  # Set this JobID as dependency of next task
  dep="$job_id"

done
