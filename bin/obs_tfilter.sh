#! /bin/bash

usage()
{
echo "obs_tfilter.sh [-d dep] [-a account] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

pipeuser="${GPMUSER}"

#initial variables
dep=
tst=
# parse args and set options
while getopts ':td:a:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG}
        ;;
    a)
        account=${OPTARG}
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

queue="-p ${GPMSTANDARDQ}"

# if obsid is empty then just print help

if [[ -z ${obsnum} ]]
then
    usage
fi

if [[ ! -z ${dep} ]]
then
    depend="--dependency=afterok:${dep}"
fi

if [[ ! -z ${GPMACCOUNT} ]]
then
    account="--account=${GPMACCOUNT}"
fi

# start the real program

script="${GPMSCRIPT}/tfilter_${obsnum}.sh"
cat "${GPMBASE}/templates/tfilter.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GPMLOG}/tfilter_${obsnum}.o%A"
error="${GPMLOG}/tfilter_${obsnum}.e%A"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
echo "singularity run ${GPMCONTAINER} ${script}" >> "${script}.sbatch"

#sub="sbatch --begin=now+5minutes --export=ALL  --time=01:00:00 --mem=10G -M ${GPMCOMPUTER} --output=${output} --error=${error}"
sub="sbatch --export=ALL  --time=00:10:00 --mem=40G -M ${GPMCOMPUTER} --output=${output} --error=${error}"
sub="${sub} ${GPMNCPULINE} ${account} ${GPMTASKLINE} ${depend} ${queue} ${script}.sbatch"
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

echo "Submitted ${script} as ${jobid} . Follow progress here:"

# Add rows to the database 'processing' table that will track the progress of this submission
${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_jobs --jobid="${jobid}" --task='tfilter' --batch_file="${script}" --obs_file="${obsnum}" --stderr="${error}" --stdout="${output}"
${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue_jobs --jobid="${jobid}" --submission_time="$(date +%s)"

echo "STDOUTs: ${output}"
echo "STDERRs: ${error}"

