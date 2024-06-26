#! /bin/bash

usage()
{
echo "obs_image.sh [-d dep] [-z] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -z         : Debugging mode: image the CORRECTED_DATA column
                instead of imaging the DATA column
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
debug=
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
    ? | : | h)
        usage
        ;;
  esac
done
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsnum=$1

queue="-p ${GPMSTANDARDQ}"
code="${GPMBASE}"

# if obsid is empty then just print help

if [[ -z ${obsnum} ]]
then
    usage
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

# start the real program

script="${GPMSCRIPT}/image_${obsnum}.sh"
cat "${GPMBASE}/templates/image.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:DEBUG:${debug}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GPMLOG}/image_${obsnum}.o%A"
error="${GPMLOG}/image_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
sbatch_script=${script}.sbatch
echo "#!/bin/bash

# GPM Version: ${GPMVERSION}
# Git commit: ${GPMGITVERSION}

#SBATCH --export=ALL
#SBATCH --time=10:00:00
#SBATCH --mem=${GPMABSMEMORY}G
#SBATCH --clusters=${GPMCOMPUTER}
#SBATCH --output=${output}
#SBATCH --error=${error}
#SBATCH ${GPMNCPULINE}
#SBATCH --account=${GPMACCOUNT}
#SBATCH --partition=${GPMSTANDARDQ}
" > ${sbatch_script}

if [ ! -z ${GPMTASKLINE} ]
then
    echo "#SBATCH ${GPMTASKLINE}" >> ${sbatch_script}
fi

if [ ! -z ${jobarray} ]
then
    echo "#SBATCH ${jobarray}" >> ${sbatch_script}
fi

echo "
source ${GPMPROFILE}

singularity run ${GPMCONTAINER} ${script}
" >> ${sbatch_script}

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

echo "Submitted ${script} as ${jobid} . Follow progress here:"

# Add rows to the database 'processing' table that will track the progress of this submission
${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_jobs --jobid="${jobid}" --task='image' --batch_file="${script}" --obs_file="${obsnum}" --stderr="${error}" --stdout="${output}"
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
#        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_job --jobid="${jobid}" --taskid="${taskid}" --task='image' --submission_time="$(date +%s)" \
#                            --batch_file="${script}" --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
#    fi
#
#    echo "$obsoutput"
#    echo "$obserror"
#done

