#! /bin/bash

usage()
{
echo "obs_calcleakage [-d dep] [-p project] [-a account] [-z] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -p project : project, (must be specified, no default)
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
while getopts ':td:a:p:' OPTION
do
    case "$OPTION" in
	d)
	    dep=${OPTARG}
	    ;;
    a)
        account=${OPTARG}
        ;;
    p)
        project=${OPTARG}
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
base="${GPMSCRATCH}/$project"
code="${GPMBASE}"

# if obsid is empty then just print help

if [[ -z ${obsnum} ]] || [[ -z $project ]] || [[ ! -d ${base} ]]
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

if [[ ! -z ${GPMACCOUNT} ]]
then
    account="--account=${GPMACCOUNT}"
fi

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l "${obsnum}" | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
else
    numfiles=1
    jobarray=''
fi

# start the real program

script="${GPMSCRIPT}/calcleakage_${obsnum}.sh"
cat "${GPMBASE}/templates/calcleakage.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:BASEDIR:${base}:g" > "${script}"

output="${GPMLOG}/calcleakage_${obsnum}.o%A"
error="${GPMLOG}/calcleakage_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

sub="sbatch --begin=now --export=ALL  --time=00:30:00 --mem=24G -M ${GPMCOMPUTER} --output=${output} --error=${error}"
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

for taskid in $(seq ${numfiles})
    do
    # rename the err/output files as we now know the jobid
    obserror=$(echo "${error}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")
    obsoutput=$(echo "${output}" | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/")

    if [[ -f ${obsnum} ]]
    then
        obs=$(sed -n -e "${taskid}"p "${obsnum}")
    else
        obs=$obsnum
    fi

    if [ "${GPMTRACK}" = "track" ]
    then
        # record submission
        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_job --jobid="${jobid}" --taskid="${taskid}" --task='calcleakage' --submission_time="$(date +%s)" \
                            --batch_file="${script}" --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
    fi

    echo "$obsoutput"
    echo "$obserror"
done

