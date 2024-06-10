#! /bin/bash

usage()
{
echo "obs_apply_cal.sh [-p project] [-d dep] [-a account] [-z] [-t] obsid
  -p project  : project, no default
  -d dep      : job number for dependency (afterok)
  -z          : Debugging mode: create a new CORRECTED_DATA column
                instead of applying to the DATA column
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  -v          : verbose mode (set -ex)
  obsid      : the obsid to process, or a text file of obsids (newline separated)" 1>&2;
exit 1;
}

pipeuser="${GPMUSER}"

#initial variables
dep=
tst=
account=
debug=

# parse args and set options
while getopts ':tzd:a:p:v' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG}
        ;;
    p)
        project=${OPTARG}
        ;;
    z)
        debug=1
        ;;
    t)
        tst=1
        ;;
    v)
        set -ex
        ;;
    ? | : | h)
        usage
        ;;
  esac
done

# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsid=$1

# if obsid is empty then just print help
if [[ -z ${obsid} ]]
then
    usage
fi


if [[ ! -z ${dep} ]]
then
    if [[ -f ${obsid} ]]
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
if [[ -f ${obsid} ]]
then
    numfiles=$(wc -l ${obsid} | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
else
    numfiles=1
    jobarray=''
fi

# Set directories
queue="-p ${GPMSTANDARDQ}"
base="${GPMSCRATCH}/${project}"


script="${GPMSCRIPT}/apply_cal_${obsid}.sh"

cat "${GPMBASE}/templates/apply_cal.tmpl" | sed -e "s:OBSNUM:${obsid}:g" \
                                       -e "s:BASEDIR:${base}:g" \
                                       -e "s:DEBUG:${debug}:g" \
                                       -e "s:PIPEUSER:${pipeuser}:g"  > ${script}

chmod 755 "${script}"

output="${GPMLOG}/apply_cal_${obsid}.o%A"
error="${GPMLOG}/apply_cal_${obsid}.e%A"

if [[ -f ${obsid} ]]
then
    output="${output}_%a"
    error="${error}_%a"
fi

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

if [[ ! -z ${GPMNCPULINE} ]]
then
    # autoflag only needs a single CPU core
    GPMNCPULINE="--ntasks-per-node=1"
fi

sub="sbatch --export=ALL ${account} --time=02:00:00 --mem=24G -M ${GPMCOMPUTER} --output=${output} --error=${error} "
sub="${sub}  ${GPMNCPULINE} ${account} ${GPMTASKLINE} ${jobarray} ${depend} ${queue} ${script}.sbatch"

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
    obserror=`echo ${error} | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/"`
    obsoutput=`echo ${output} | sed -e "s/%A/${jobid}/" -e "s/%a/${taskid}/"`

    if [[ -f ${obsid} ]]
    then
        obs=$(sed -n -e ${taskid}p ${obsid})
    else
        obs=$obsid
    fi

    if [ "${GPMTRACK}" = "track" ]
    then
        # record submission
        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue --jobid=${jobid} --taskid=${taskid} --task='apply_cal' --submission_time=`date +%s` --batch_file=${script} \
                            --obs_id=${obs} --stderr=${obserror} --stdout=${obsoutput}
    fi

    echo $obsoutput
    echo $obserror
done
