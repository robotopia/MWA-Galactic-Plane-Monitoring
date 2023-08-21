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

### Add an observation's metadata to the database

```
singularity exec ${GXCONTAINER} ./gpm_track.py import_obs --obs_id [OBS_ID]
```
