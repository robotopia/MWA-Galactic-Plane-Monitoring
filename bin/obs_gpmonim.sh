#! /bin/bash

usage()
{
echo "obs_gpmonim.sh [-d dep] [-p project] [-a account] [-z] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -p project : project, (must be specified, no default)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  obsnum     : the obsid of the calibrator, the data around which will be processed." 1>&2;
exit 1;
}

pipeuser="${GPMUSER}"

#initial variables
dep=
tst=
debug=
# parse args and set options
while getopts ':tzd:a:p:' OPTION
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

# start the real program

output="${GPMLOG}/gpmonim_${obsnum}.o%A"
error="${GPMLOG}/gpmonim_${obsnum}.e%A"
script="${GPMSCRIPT}/gpmonim_${obsnum}.sh"

cat "${GPMBASE}/templates/gpmonim.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:DEBUG:${debug}:g" \
                                 -e "s:SUBMIT:${script}:g" \
                                 -e "s:ERROR:${error}:g" \
                                 -e "s:OUTPUT:${output}:g" \
                                 -e "s:QUEUE:${queue}:g" \
                                 -e "s:ACCOUNT:${account}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"


if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

sub="sbatch --begin=now+5minutes --export=ALL  --time=01:00:00 --mem=${GPMABSMEMORY}G -M ${GPMCOMPUTER} --output=${output} --error=${error}"
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

# Not sure what task we should use considering this spawns a job that submits more tasks
#    if [ "${GPMTRACK}" = "track" ]
#    then
#        # record submission
#        ${GPMCONTAINER} track_task.py queue --jobid="${jobid}" --taskid="${taskid}" --task='' --submission_time="$(date +%s)" \
#                            --batch_file="${script}" --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
#    fi

    echo "$obsoutput"
    echo "$obserror"
done
