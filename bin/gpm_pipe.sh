#! /bin/bash

usage()
{
echo "gpm_pipe [options] [-h] commands obsid_or_file
  options     : Options passed to the listed commands. The command-specific options are:

                Command    | Option       | Description
                -----------+--------------+--------------------------------------
                [some/all] | -f           | Force. Whatever that means for each command, do it.
                           |              | (Currently only for \"manta\")
                           | -t           | Test. Whatever that means for each command, do it.
                           | -z           | Debugging mode. Whatever that means for each command,
                           |              | do it.
                           | -d DEP       | Make the first job dependent on DEP.
                           | -v           | Verbose mode
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
                tfilter    | -r runname   | The 'project' name to use when uploading candidates. If
                           |              | not supplied, will default to \$GPMRUNNAME (currently set
			   |              | to \"$GPMRUNNAME\". <-- If this is empty, set it in your
                           |              | profile).

  commands    : A string of space-delimited commands to run, as a dependency chain, in the order in which they are listed.
                e.g. \"image postimage\" will run \"obs_image.sh\" followed by \"obs_postimage.sh\". Available commands:
                    apply_cal, autocal, autoflag, calcleakage, image,
		    postimage, tfilter, transient, uvflag

  obsid_or_file : The obsid of the observation to be processed OR a file containing one or more newline-separated obsids

  EXAMPLE:

      gpm_pipe.sh \"autoflag apply_cal uvflag image transient postimage-I postimage-V tfilter\" 1234567890" 1>&2;
}

commands=

zoption=
ioption=
Foption=
Soption=
Poption=
toption=
voption=
roption=
init_depend=

# parse args and set options
while getopts 'd:hs:k:e:gc:ziF:S:P:r:ftv' OPTION
do
    case "$OPTION" in
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
        t)
            toption="-t";;
        v)
            set -ex
            voption="-v";;
        d)
            init_depend="-d ${OPTARG}";;
        r)
            roption="-r ${OPTARG}";;
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

# Set the obsid_or_file to be the list of all remaining arguments
shift
obsid_or_file="$1"
if [[ -z $obsid_or_file ]]
then
    usage
    echo "No obsid or file supplied. Nothing to be done."
    exit 1
fi

# Common singularity command to run the python code
SINGCMD="singularity exec ${GPMCONTAINER} "

depend=$init_depend
if [[ ! -z $depend ]]
then
    echo " Dependent on: $depend"
fi

# Loop through commands
for cmd in $commands
do
    # Construct options
    case "$cmd" in
        acacia)
            options="$toption" ;;
        autoflag)
            options="$toption" ;;
        autocal)
            options="$ioption $toption $Foption $Soption" ;;
        apply_cal)
            options="$zoption $toption $voption" ;;
        calcleakage)
            options="$toption" ;;
        image)
            options="$zoption $toption" ;;
        postimage)
            options="$toption $Poption" ;;
        restore)
            options= ;;
        tfilter)
            options="$toption $roption" ;;
        transient)
            options="$zoption $toption" ;;
        uvflag)
            options="$zoption $toption" ;;
        uvsub)
            options="$zoption $toption" ;;
        *)
            echo "unrecognised command: $cmd. Exiting"
            exit 1 ;;
    esac

    # Construct the whole command
    obs_cmd="obs_${cmd}.sh ${depend} ${options} $obsid_or_file"
    echo "Running $cmd: $obs_cmd"

    # Run it, and parse the output for the job number (to use as a dependency for the next job)
    dep=($(${obs_cmd} | tee /dev/tty))
    if [[ "$?" != 0 ]]
    then
        echo "Command \"${cmd}\" failed. Stopping..."
	exit 1
    fi
    depend="-d ${dep[3]}"
done
