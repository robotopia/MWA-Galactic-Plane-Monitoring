#! /bin/bash

usage()
{
echo "obs_acacia.sh [-d dep] [-t] [-a obstype] obsnum
  -d dep     : job number for dependency
  -D deptype : Force job dependency type
               Default is \"afterok\" for single jobs, and \"aftercorr\"
	       for array jobs.
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  -a obstype : observation type, defining what gets uploaded. Options are:
               \"target\"      :  Upload initial image products
	       \"warp\"        :  Upload 'warp' image products
	       \"calibration\" :  Upload calibration solutions and images
	       (Default = \"target\")
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

pipeuser="${GPMUSER}"

#initial variables
dep=
tst=
obstype=target
deptype=
# parse args and set options
while getopts ':td:D:a:' OPTION
do
    case "$OPTION" in
    d)
        dep=${OPTARG}
        ;;
    D)
        deptype=${OPTARG}
        ;;
    t)
        tst=1
        ;;
    a)
        obstype=${OPTARG}
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
    if [[ -z ${deptype} ]]
    then
        if [[ -f ${obsnum} ]]
        then
            deptype=aftercorr
        else
            deptype=afterok
        fi
    fi
    depend="--dependency=${deptype}:${dep}"
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

script="${GPMSCRIPT}/acacia_${obstype}_${obsnum}.sh"
cat "${GPMBASE}/templates/acacia.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                             -e "s:PIPEUSER:${pipeuser}:g" \
                                             -e "s:OBSTYPE:${obstype}:g" > "${script}"

output="${GPMLOG}/acacia_${obsnum}.o%A"
error="${GPMLOG}/acacia_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
sbatch_script=${script}.sbatch
echo "#!/bin/bash

# GPM Version: ${GPMGITVERSION}

#SBATCH --export=ALL
#SBATCH --time=01:00:00
#SBATCH --clusters=${GPMCOMPUTER}
#SBATCH --output=${output}
#SBATCH --error=${error}
#SBATCH --cpus-per-task=1
#SBATCH --account=${GPMACCOUNT}
#SBATCH --partition=${GPMCOPYQ}
" > ${sbatch_script}

if [ ! -z ${jobarray} ]
then
    echo "#SBATCH ${jobarray}" >> ${sbatch_script}
fi

RCLONE_MODULE="$(module -t --default -r avail "^rclone$" 2>&1 | grep -v ':' | head -1)"

echo "
source ${GPMPROFILE}

module load ${RCLONE_MODULE}

${script}
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
${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_jobs --jobid="${jobid}" --task='acacia' --batch_file="${script}" --obs_file="${obsnum}" --stderr="${error}" --stdout="${output}"
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
#        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py create_job --jobid="${jobid}" --taskid="${taskid}" --task='acacia' --submission_time="$(date +%s)" \
#                            --batch_file="${script}" --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
#    fi
#
#    echo "$obsoutput"
#    echo "$obserror"
#done

