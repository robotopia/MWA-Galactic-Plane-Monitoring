
# Change Log

## v0.4 - 2024-07-03

### Changed

- Added automatic detection of default singularity module when loading profile
- Added git-tag based versioning to be made available in scripts
- Reverted to looking for available calibration solution on disk (instead of trying to automatically pull it from Acacia, for example)
- Added `gpm_automatic_processing.sh`, which so far only checks the MWA services for any new observations that have been taken since the most recent observation in the database
- Added a `-d` (dependency) option to `gpm_pipe.sh`
- Added an `obs_acacia.sh` script for archiving imaged observations to Acacia
- Added a draft script (not yet working) for making an all-sky image
- Removed the `-c` option from `obs_apply_cal.sh`
- Removed `-p` options from all scripts (the epoch is now always automatically determined from the database)
- When submitting multi-obs jobs, database updates are now also done in bulk (instead of one taskid at a time)
- Added `GPMMAXARRAYJOBS` environment variable to profile, for throttling SLURM queue usage
- Changed `obs_image.sh` so that its sbatch script contains a full set of SLURM directives
- Removed deprecated `obs_manta.sh`
- Created new Django application to sit on top of database
- Changed incorrect clean settings (`msigma` now set to 5, `tsigma` now set to 3), and other potential errors in `wsclean` calls

## v0.3 - 2024-01-11
 
### Changed

- Upgraded `wsclean` version in container to v3.4
- Added documentation describing the overall pipeline
- Replaced the `mantaray` client with `giant-squid`
- Download workflow now consistent with [recommended guidelines](https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/65405030/MWA+ASVO+Use+with+HPC+Systems).

### Fixed

- Sky model is now *always* cropped

## v0.2 - 2023-08-04

### Added

- `gpm_track.py` functionality for labelling obs-cal pairs as usable or not
 
### Changed

- Made this pipeline independent from the GLEAM-X pipeline
- Removed local "auxilliary" (Python) scripts from container, and added paths to them where necessary
- Replaced `gpmonim` with `gpm_obsbycal.sh`.
- Added documentation about previous calibration efforts

## v0.1 - 2022-08-17
 
### Added
   
- Initial working monitoring code, designed to process MWA data as soon as they
  become available
- Detailed sky model of Cygnus A
- 5-minute cadence search plots
- Leakage screen fitter
