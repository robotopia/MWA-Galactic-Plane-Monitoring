#! /bin/bash

usage()
{
echo "gpm_pipe [options] [-h] commands obsid [obsid ...]
  options     : Options passed to the listed commands. The command-specific options are:

                Command    | Option       | Description
                -----------+--------------+--------------------------------------
                [some/all] | -f           | Force. Whatever that means for each command, do it.
                           |              | (Currently only for \"manta\")
                           | -t           | Test. Whatever that means for each command, do it.
                           | -z           | Debugging mode. Whatever that means for each command,
                           |              | do it.
                manta      | -s timeres   | time resolution in sec. default = 2 s
                           | -k freqres   | freq resolution in KHz. default = 40 kHz
                           | -e edgeflag  | number of edge band channels flagged. default = 80
                           | -g           | download gpubox fits files instead of measurement sets
                apply_cal  | -c calfile   | path to (.bin) calibration solutions file
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
                    apply_cal, autocal, autoflag, calcleakage, image, manta, postimage,
                    postimageI, postimageV, tfilter, transient, uvflag

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
then
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

    echo "============================="
    echo " OBSID: $obsid"

    # Loope through commands
    for cmd in $commands
    do
        # Construct options
        case "$cmd" in
            manta)
                options="$soption $koption $eoption $goption $toption $foption" ;;
            autoflag)
                options="$toption" ;;
            autocal)
                options="$ioption $toption $Foption $Soption" ;;
            apply_cal)
                options="$coption $zoption $toption" ;;
            calcleakage)
                options="$toption" ;;
            image)
                options="$zoption $toption" ;;
            postimage)
                options="$toption $Poption" ;;
            postimageI)
                options="$toption" ;;
            postimageV)
                options="$toption" ;;
            tfilter)
                options="$toption" ;;
            transient)
                options="$zoption $toption" ;;
            uvflag)
                options="$zoption $toption" ;;
            *)
                echo "unrecognised command: $cmd. Exiting"
                exit 1 ;;
        esac

        # Construct the whole command
        obs_cmd="obs_${cmd}.sh ${depend} ${options} -p $epoch $obsid"
        echo "-----------------------------"
        echo "Running $cmd: $obs_cmd"

        # Run it, and parse the output for the job number (to use as a dependency for the next job)
        dep=($(${obs_cmd} | tee /dev/tty))
        if [[ "$?" != 0 ]]
        then
            echo "Command \"${cmd}\" failed for ${obsid}. Moving to next obsid..."
            break
        fi
        depend="-d ${dep[3]}"
    done
done