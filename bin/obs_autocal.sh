#! /bin/bash

# set -x

usage()
{
echo "obs_autocal.sh [-d dep] [-F frac] [-S sfrac] [-t] obsnum
  -p project : project, no default
  -d dep     : job number for dependency (afterok)
  -i         : disable the ionospheric metric tests (default = False)
  -t         : test. Don't submit job, just make the batch file
               and then return the submission command
  -F frac    : the acceptable fraction of spectrum that may be flagged in a calibration
               solution file before it is marked as bad. Value between 0 - 1. (default = 0.25)
  -S sfrac   : the acceptable fraction of a segmented spectrum that may be flagged in a 
               calibration solution file before it is flagged as bad. Typical GLEAM-X
               processing has four sub-bands, so there are four segments. If a single 
               segment has more then SFRAC flagged it is marked as bad. (default = 0.4) 
  obsnum     : the obsid to process, or a text file of obsids (newline separated). 
               A job-array task will be submitted to process the collection of obsids. " 1>&2;
exit 1;
}

pipeuser=${GPMUSER}

dep=
tst=
ion=1
frac=0.25
sthresh=0.4

# parse args and set options
while getopts ':tia:d:p:f:s:' OPTION
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
	i)
	    ion=
	    ;;
	t)
	    tst=1
	    ;;
    F)
        frac=${OPTARG}
        ;;
    S) 
        sthresh=${OPTARG}
        ;;
	? | : | h)
	    usage
	    ;;
  esac
done
# set the obsid to be the first non option
shift  "$(($OPTIND -1))"
obsnum=$1

# if obsid or project are empty then just print help
if [[ -z ${obsnum} || -z ${project} ]]
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
else
    numfiles=1
    jobarray=''
fi

queue="-p ${GPMSTANDARDQ}"
datadir="${GPMSCRATCH}/$project"

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

script="${GPMSCRIPT}/autocal_${obsnum}.sh"

cat "${GPMBASE}/templates/autocal.tmpl" | sed -e "s:OBSNUM:${obsnum}:g" \
                                     -e "s:DATADIR:${datadir}:g" \
                                     -e "s:IONOTEST:${ion}:g" \
                                     -e "s:PIPEUSER:${pipeuser}:g" \
                                     -e "s:FRACTION:${frac}:g" \
                                     -e "s:STHRESH:${sthresh}:g" > "${script}"


output="${GPMLOG}/autocal_${obsnum}.o%A"
error="${GPMLOG}/autocal_${obsnum}.e%A"

if [[ -f ${obsnum} ]]
then
   output="${output}_%a"
   error="${error}_%a"
fi

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > ${script}.sbatch
echo "singularity run ${GPMCONTAINER} ${script}" >> ${script}.sbatch

sub="sbatch --begin=now+5minutes --export=ALL  --time=04:00:00 --mem=${GPMABSMEMORY}G -M ${GPMCOMPUTER} --output=${output} --error=${error}"
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
        ${GPMCONTAINER} ${GPMBASE}/gpm_track.py queue --jobid="${jobid}" --taskid="${taskid}" --task='calibrate' --submission_time="$(date +%s)" --batch_file="${script}" \
                            --obs_id="${obs}" --stderr="${obserror}" --stdout="${obsoutput}"
    fi

    echo "$obsoutput"
    echo "$obserror"
done
