#! /bin/bash

usage()
{
echo "gpm_onecal_manyobs.sh [options] [-h] commands obsid [obsid ...]
  options     : Options passed to the listed commands. The command-specific options are:

                Command    | Option       | Description
                -----------+--------------+--------------------------------------
                [all]      | -f           | Force. Whatever that means for each command, do it.
                           | -t           | Test. Whatever that means for each command, do it.
                manta      | -s timeres   | time resolution in sec. default = 2 s
                           | -k freqres   | freq resolution in KHz. default = 40 kHz
                           | -e edgeflag  | number of edge band channels flagged. default = 80
                           | -g           | download gpubox fits files instead of measurement sets
                apply_cal  | -c calfile   | path to (.bin) calibration solutions file
                           | -z           | Debugging mode: create a new CORRECTED_DATA column
                           |              | instead of applying to the DATA column
                autocal    | -i           | Disable the ionospheric tests (default = False)
                           | -F frac      | the acceptable fraction of spectrum that may be flagged
                           |              | in a calibration solution file before it is marked as
                           |              | bad. Value between 0 - 1. (default = 0.25)
                           | -S sfrac     | the acceptable fraction of a segmented spectrum that may
                           |              | be flagged in a calibration solution file before it is
                           |              | flagged as bad. Typical GLEAM-X processing has four
                           |              | sub-bands, so there are four segments. If a single
                           |              | segment has more then SFRAC flagged it is marked as bad.
                           |              | (default = 0.4)
                postimage  | -P pol       | which polarisation to process (default: I)

  commands    : A string of space-delimited commands to run, as a dependency chain, in the order in which they are listed.
                e.g. \"image postimage\" will run \"obs_image.sh\" followed by \"obs_postimage.sh\". Available commands:
                    apply_cal, autocal, autoflag, image, manta, postimage, tfilter, transient, uvflag

  obsid       : The obsid(s) of the observation(s) to be processed" 1>&2;
}

commands=

soption=
koption=
eoption=
goption=
coption=
zoption=
ioption=
Foption=
Soption=
Poption=
foption=
toption=

# parse args and set options
while getopts 'hs:k:e:gc:ziF:S:P:ft' OPTION
do
    case "$OPTION" in
        s)
            soption="-s ${OPTARG}";;
        k)
            koption="-k ${OPTARG}";;
        e)
            eoption="-e ${OPTARG}";;
        g)
            goption="-g";;
        c)
            coption="-c ${OPTARG}";;
        z)
            zoption="-z";;
        i)
            ioption="-i";;
        F)
            Foption="-F ${OPTARG}";;
        S)
            Soption="-S ${OPTARG}";;
        P)
            Poption="-P ${OPTARG}";;
        f)
            foption="-f";;
        t)
            toption="-t";;
        h)
            usage
            exit 1;;
        *)
            echo "Unrecognised option"
            usage
            exit 1;;
    esac
done

# Get the list of commands next
shift  "$(($OPTIND -1))"
commands="$1"
if [[ -z $commands ]]
    usage
    echo "No commands supplied. Nothing to be done."
    exit 1
fi

# Set the obsids to be the list of all remaining arguments
shift
obsids="$*"
if [[ -z $obsids ]]
then
    usage
    echo "No obsids supplied. Nothing to be done."
    exit 1
fi

# Common singularity command to run the python code
SINGCMD="singularity exec ${GPMCONTAINER} "

for obsid in $obsids
do
    # Start with no dependency
    depend=

    # Get the obsid's epoch from the database to use as the "project directory"
    epoch=$(${SINGCMD} "${GPMBASE}/gpm_track.py" obs_epoch --obs_id $obsid)
    datadir="${GPMSCRATCH}/${epoch}"
    mkdir -p $datadir
    cd $datadir

    # Loope through commands
    for cmd in $commands
    do
        echo "Running $cmd: "
        # Construct options
        case "$cmd" in
            manta)
                options="$soption $koption $eoption $goption $toption $foption" ;;
        esac


        dep=($(obs_{$cmd}.sh ${depend} ${options} -p $epoch $obsid))
        if [[ "$?" != 0 ]]
            echo "obs_${cmd}.sh failed. Stopping for ${obsid}"
            continue # FIX ME!!
        fi
        depend="-d ${dep[3]}"
        echo "ObsID $obsid (manta): ${dep[*]}"

        cmd="obs_autoflag.sh ${depend} -p ${epoch} $obsid"
        echo "Running autoflag: $cmd"

        dep=($(${cmd}))
        echo "ObsID $obsid (autoflag): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_apply_cal.sh ${depend} -p "${epoch}" -c "$caldir/$calfile" -z  $obsid))
        echo "ObsID $obsid (apply_cal): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_uvflag.sh ${depend} -p "${epoch}" -z $obsid))
        echo "ObsID $obsid (uvflag): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_image.sh ${depend} -p "${epoch}" -z $obsid))
        echo "ObsID $obsid (image): ${dep[*]}"
        depend="-d ${dep[3]}"
        dep=($(obs_transient.sh ${depend} -p "${epoch}" -z $obsid))
        echo "ObsID $obsid (transient): ${dep[*]}"
        depend="-d ${dep[3]}"
        depp=($(obs_postimage.sh ${depend} -p "${epoch}" -P I $obsid))
        echo "ObsID $obsid (postimage-I): ${depp[*]}"
        deppp=($(obs_postimage.sh ${depend} -p "${epoch}" -P V $obsid))
        echo "ObsID $obsid (postimage-V): ${deppp[*]}"
        dep=($(obs_tfilter.sh ${depend} -p "${epoch}" $obsid))
        echo "ObsID $obsid (tfilter): ${dep[*]}"
    done
done
