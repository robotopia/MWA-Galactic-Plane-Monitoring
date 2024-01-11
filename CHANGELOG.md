
# Change Log

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
