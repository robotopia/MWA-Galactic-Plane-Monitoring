#!/bin/bash

#set -eux

#################
# Initial setup #
#################

# Hard-coded "constants" for this project
MWA_PROJECT=G0080

# A handy "alias" for running the database-interaction script
gpmdb="singularity exec $GPMCONTAINER $GPMBASE/gpm_track.py"

# Where the output of this log will go
LOG=${GPMLOG}/gpm_automatic_processing_$(date +'%Y-%m-%dT%T').log
exec 2>&1 1>${LOG}  # <--- redirects output of this script to the log file

# Parse the argument as the number of look-back hours to consider for processing
if [[ -z "$1" ]]
then
  NHOURS=24
else
  NHOURS=$1
fi

# Initial messages to the user
echo "----------------------------------"
echo "AUTOMATIC GPM PIPELINE ${GPMGITVERSION}"
echo "----------------------------------"
echo "Started at: $(date)"
echo "This log being written to: ${LOG}"
echo

#############################################################################
# Find the new observations that have taken since the last time this script #
# was run, and import them into the database.                               #
#############################################################################

# Get the most recent obsid from the database
LAST_OBS=$(${gpmdb} last_obs)

echo "The last observation in the database is currently $LAST_OBS"
echo

# Get any observations that have occurred since then

## The MWA metadata API's query parameter "mintime" is inclusive, so add 1 to
## the obs_id so that the last one _isn't_ included
LAST_OBS_PLUS_ONE=$((${LAST_OBS}+1))

echo -n "Searching for available observations from ${LAST_OBS_PLUS_ONE} onwards... "
MWA_RESPONSE="$(curl https://ws.mwatelescope.org/metadata/find?projectid=${MWA_PROJECT}\&mintime=${LAST_OBS_PLUS_ONE}\&future=0 2>/dev/null)"

## If there are no matching observations, the above curl command will return HTML.
## We will use a slightly hacky test to tell if this has happened, by grepping for "html" in the output
if echo "${MWA_RESPONSE}" | grep -q html
then
  echo "Found no new observations"
else
  NEW_OBS="$(echo "${MWA_RESPONSE}" | jq '.[] | .[0]')"
  NUM_NEW_OBS=$(echo "${NEW_OBS}" | wc -w)

  ## Import them into the database

  echo "Found ${NUM_NEW_OBS} new observations (from $(echo "${NEW_OBS}" | head -1) to $(echo "${NEW_OBS}" | tail -1))"
  echo "Importing them into the database:"
  for obsid in ${NEW_OBS}
  do
    echo -n "  - "
    ${gpmdb} import_obs --obs_id $obsid 2>&1
  done
fi

echo

#####################################################################
# Get the observations to be processed within the last NHOURS hours #
#####################################################################

echo "----------------------------------"
echo -n "Retrieving observations to be processed within the last ${NHOURS} hours... "
TO_PROCESS=$(${gpmdb} recent_obs --nhours=${NHOURS})
NUM_TO_PROCESS=$(echo "${TO_PROCESS}" | wc -w)
echo "Found ${NUM_TO_PROCESS}"
