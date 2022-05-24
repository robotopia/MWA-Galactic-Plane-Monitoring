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

queue="-p ${GXSTANDARDQ}"
base="${GPMSCRATCH}/$project"

# if obsid is empty then just print help

if [[ -z ${obsnum} ]] || [[ -z $project ]] || [[ ! -d ${base} ]]
then
    usage
fi

if [[ ! -z ${dep} ]]
then
    depend="--dependency=afterok:${dep}"
fi

if [[ ! -z ${GXACCOUNT} ]]
then
    account="--account=${GXACCOUNT}"
fi

# start the real program

output="${GPMLOG}/gpmonim_${obsnum}.o%A"
error="${GPMLOG}/gpmonim_${obsnum}.e%A"
script="${GPMSCRIPT}/gpmonim_${obsnum}.sh"

cat "${GPMBASE}/templates/gpmonim.tmpl" | sed -e "s:CALID:${obsnum}:g" \
                                 -e "s:BASEDIR:${base}:g" \
                                 -e "s:DEBUG:${debug}:g" \
                                 -e "s:SUBMIT:${script}:g" \
                                 -e "s:ERROR:${error}:g" \
                                 -e "s:OUTPUT:${output}:g" \
                                 -e "s:QUEUE:${queue}:g" \
                                 -e "s:ACCOUNT:${account}:g" \
                                 -e "s:PIPEUSER:${pipeuser}:g" > "${script}"

chmod 755 "${script}"

# sbatch submissions need to start with a shebang
echo '#!/bin/bash' > "${script}.sbatch"
echo "singularity run ${GXCONTAINER} ${script}" >> "${script}.sbatch"

sub="sbatch --begin=now+5minutes --export=ALL  --time=01:00:00 --mem=${GXBSMEMORY}G -M ${GXCOMPUTER} --output=${output} --error=${error}"
sub="${sub} ${GXCPULINE} ${account} ${GXTASKLINE} ${depend} ${queue} ${script}.sbatch"
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
