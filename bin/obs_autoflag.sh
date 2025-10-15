#! /bin/bash

usage()
{
echo "obs_autoflag.sh [-d dep] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
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
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsnum=$1

# if obsid is empty then just ping help
if [[ -z ${obsnum} ]]
then
    usage
fi

# Get job enviroment
curl -X GET -H "Authorization: Token ${GPMDBTOKEN}" -H "Accept: application/json" "https://gpm.mwa-image-plane.cloud.edu.au/processing/api/load_job_environment?pipeline=calibrate&task=flag"

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l "${obsnum}" | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
else
    numfiles=1
    jobarray=''
fi

queue="-p ${GPMSTANDARDQ}"

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

script="${GPMSCRIPT}/autoflag_${obsnum}.sh"

cat "${GPMBASE}/templates/autoflag.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" > "${script}"


output="${GPMLOG}/autoflag_${obsnum}.o%A"
error="${GPMLOG}/autoflag_${obsnum}.e%A"
if [[ -f ${obsnum} ]]
then
    output="${output}_%a"
    error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

sub="sbatch --begin=${GPMBEGIN} --export=ALL --time=${GPMTIME} -M ${GPMCLUSTER} --output=${output} --error=${error} "
sub="${sub}  --ntasks-per-node=${GPMNTASKSPERNODE} --account=${GPMACCOUNT} ${jobarray} ${depend} ${queue} ${script}.sbatch"

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

