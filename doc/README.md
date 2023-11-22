# Documentation

## Load the GPM profile

Make a copy of the file `GP-Monitor.profile` and edit it according to the
computing environment that is being used to run the pipeline. Do not git-track
the copied file.

For example,

```
cp GP-Monitor.profile GP-Monitor-garrawarla.profile
# [edit GP-Monitor-garrawarla.profile]
```

Then, `source` it to "load the profile":

```
source GP-Monitor-garrawarla.profile
```

## Database operations

Once the [profile has been loaded](#load-the-gpm-profile), the environment variable `GPMCONTAINER` contains the path to a singularity container in which various operations, jobs, and scripts can be run, including the database scripts described in this section.
To run a command inside the container, preface the command with
```
singularity exec $GPMCONTAINER ...
```
In addition, be aware that the database scripts themselves will not (by default) be in your path, so you will typically need to give the path to their location as well.
For example, even though the documentation below describes commands such as
```
gpm_track.py import_obs --obs_id 1346053400
```
in reality, the command you will run will be
```
singularity exec $GPMCONTAINER $GPMBASE/gpm_track.py obs_processing --obs_id 1346053400
```

### Add an observation's metadata to the database

```
gpm_track.py import_obs --obs_id [OBS_ID]
```

### Assign a calibration obs to an observation

```
gpm_track.py obs_calibrator --obs_id [OBS_ID] --cal_id [CAL_ID]
```

### Signal that a calibration can/cannot be transferred to a particular observation

```
gpm_track.py update_apply_cal --obs_id [OBS_ID] --cal_id [CAL_ID] --field usable --value [0 or 1]
```

(`--value 0` for "cannot be transferred", `--value 1` for "can be transferred")

To add a note about why,

```
gpm_track.py update_apply_cal --obs_id [OBS_ID] --cal_id [CAL_ID] --field notes --value "[Some notes here]"
```

### Check the processing history of a particular observation

This only reports processing steps that have been run by you (i.e. `$GPMUSER`):
```
gpm_track.py obs_processing --obs_id [OBS_ID]
```

### Get a summary of the processing of a particular Epoch

This only reports processing steps that have been run by you (i.e. `$GPMUSER`):
```
gpm_track.py epoch_processing --epoch [EPOCH]
```

An example of a valid epoch name is `Epoch0123`.
