#! /bin/bash

usage()
{
echo "obs_apply_cal.sh [-p project] [-d dep] [-a account] [-z] [-t] obsnum
  -p project  : project, no default
  -d dep      : job number for dependency (afterok)
  -z          : Debugging mode: create a new CORRECTED_DATA column
                instead of applying to the DATA column
  -t          : test. Don't submit job, just make the batch file
                and then return the submission command
  obsnum      : the obsid to process, or a text file of obsids (newline separated)" 1>&2;
exit 1;
}

pipeuser="${GPMUSER}"

#initial variables
dep=
calfile=
tst=
account=
debug=

# parse args and set options
while getopts ':tzd:a:c:p:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG}
        ;;
	c)
	    calfile=${OPTARG}
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

# Get the associated calfile
calfile="$(aux_getcal.sh $obsid)"
if [[ $? != 0 ]]
then
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

if [[ ! -z ${GPMACCOUNT} ]]
then
    account="--account=${GPMACCOUNT}"
fi

# Establish job array options
if [[ -f ${obsnum} ]]
then
    numfiles=$(wc -l ${obsnum} | awk '{print $1}')
    jobarray="--array=1-${numfiles}"
else
    numfiles=1
    jobarray=''
fi

# Set directories
queue="-p ${GPMSTANDARDQ}"
base="${GPMSCRATCH}/${project}"

if [[ ! -f "$calfile" ]]
then
    echo "Could not find calibrator file"
    echo "looked for $calfile"
    exit 1
fi


script="${GPMSCRIPT}/apply_cal_${obsnum}.sh"

cat "${GPMBASE}/templates/apply_cal.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                       -e "s:BASEDIR:${base}:g" \
                                       -e "s:DEBUG:${debug}:g" \
                                       -e "s:CALFILE:${calfile}:g" \
                                       -e "s:PIPEUSER:${pipeuser}:g"  > ${script}

chmod 755 "${script}"

output="${GPMLOG}/apply_cal_${obsnum}.o%A"
error="${GPMLOG}/apply_cal_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
    output="${output}_%a"
    error="${error}_%a"
fi

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

if [ ! -z ${GPMNCPULINE} ]
then
    # autoflag only needs a single CPU core
    GPMNCPULINE="--ntasks-per-node=1"
fi

sub="sbatch --begin=now+1minutes  --export=ALL ${account} --time=02:00:00 --mem=24G -M ${GPMCOMPUTER} --output=${output} --error=${error} "
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

    if [[ -f ${obsnum} ]]
    then
        obs=$(sed -n -e ${taskid}p ${obsnum})
    else
        obs=$obsnum
    fi

    if [ "${GPMTRACK}" = "track" ]
    then
        # record submission
        ${GPMCONTAINER} track_task.py queue --jobid=${jobid} --taskid=${taskid} --task='apply_cal' --submission_time=`date +%s` --batch_file=${script} \
                            --obs_id=${obs} --stderr=${obserror} --stdout=${obsoutput}
    fi

    echo $obsoutput
    echo $obserror
done
