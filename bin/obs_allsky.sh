#! /bin/bash

usage()
{
echo "obs_allsky.sh [-d dep] [-p project] [-z] [-t] obsnum
  -d dep     : job number for dependency (afterok)
  -p project : project, (must be specified, no default)
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
while getopts ':tzd:p:' OPTION
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

script="${GPMSCRIPT}/allsky_${obsnum}.sh"
cat "${GPMBASE}/templates/allsky.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:DEBUG:${debug}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

output="${GPMLOG}/allsky_${obsnum}.o%A"
error="${GPMLOG}/allsky_${obsnum}.e%A"

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
#SBATCH --time=05:00:00
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
        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue --jobid="${jobid}" --taskid="${taskid}" --task='allsky' --submission_time="$(date +%s)" \
                            --batch_file="${script}" --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
    fi

    echo "$obsoutput"
    echo "$obserror"
done
