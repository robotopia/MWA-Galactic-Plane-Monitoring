#! /bin/bash

# set -x

usage()
{
echo "obs_uvsub.sh [-d dep] [-a account] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  -z         : Debug mode, so adjusts the CORRECTED_DATA column
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

pipeuser=${GPMUSER}

dep=
tst=
debug=

# parse args and set options
while getopts ':ta:d:z' OPTION
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
    z)
        debug=1
        ;;
	? | : | h)
	    usage
	    ;;
  esac
done
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsnum=$1

# if obsid is empty then just print help
if [[ -z ${obsnum} ]]
then
    usage
fi

if [[ ! -z ${GPMACCOUNT} ]]
then
    account="--account=${GPMACCOUNT}"
fi

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l "${obsnum}" | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
    if [ ! -z ${GPMMAXARRAYJOBS} ]
    then
        jobarray="${jobarray}%${GPMMAXARRAYJOBS}"
    fi
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

script="${GPMSCRIPT}/uvsub_${obsnum}.sh"

cat "${GPMBASE}/templates/uvsub.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                     -e "s:DEBUG:${debug}:g" \
                                     -e "s:PIPEUSER:${pipeuser}:g" > "${script}"


output="${GPMLOG}/uvsub_${obsnum}.o%A"
error="${GPMLOG}/uvsub_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "srun --cpus-per-task=1 --ntasks=1 --ntasks-per-node=1  singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

if [ ! -z ${GPMNCPULINE} ]
then
    # autoflag only needs a single CPU core
    GPMNCPULINE="--ntasks-per-node=1"
fi

sub="sbatch --begin=now+5minutes --export=ALL  --time=06:00:00 --mem=50G -M ${GPMCOMPUTER} --output=${output} --error=${error}"
sub="${sub} ${GPMNCPULINE} ${account} ${GPMTASKLINE} ${jobarray} ${depend} ${queue} ${script}.sbatch"
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
${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_jobs --jobid="${jobid}" --task='uvsubtract' --batch_file="${script}" --obs_file="${obsnum}" --stderr="${error}" --stdout="${output}"
${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue_jobs --jobid="${jobid}" --submission_time="$(date +%s)"

echo "STDOUTs: ${output}"
echo "STDERRs: ${error}"

#for taskid in $(seq ${numfiles})
#    do
#    # rename the err/output files as we now know the jobid
#    obserror=$(echo "${error}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")
#    obsoutput=$(echo "${output}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")
#
#    if [[ -f ${obsnum} ]]
#    then
#        obs=$(sed -n -e "${taskid}"p "${obsnum}")
#    else
#        obs=$obsnum
#    fi
#
#    if [ "${GPMTRACK}" = "track" ]
#    then
#        # record submission
#        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_job --jobid="${jobid}" --taskid="${taskid}" --task='uvsubtract' --submission_time="$(date +%s)" --batch_file="${script}" \
#                            --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
#    fi
#
#    echo "$obsoutput"
#    echo "$obserror"
#done
