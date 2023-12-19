# Observation Pipeline - Transients
## autoflag
```
flagantennae ${obsnum}.ms $flags
```
## apply_cal
_See aux_getcal_

In production mode, apply to Data column:
```
 applysolutions \
                -nocopy \
                ${obsnum}.ms \
                "${calfile}"
```
## uvflag
```
ms_flag_by_uvdist.py "${obsnum}.ms" DATA -a
```

## uvsub
A template script to generate a model of a-team sources that will be subtracted from the visibility dataset. The idea is to make small images around a-team sources which that than subtracted from the visibilities. We are using wsclean to first chgcenter and the clean a small region arount the source. This is then subtracted from the column Data.
```
wget -O "${metafits}" "http://ws.mwatelescope.org/metadata/fits?obs_id=${obsnum}"
```
Check whether the phase centre has already changed. Calibration will fail if it has, so measurement set must be shifted back to its original position.
```
current=$(chgcentre "${obsnum}.ms")
coords=$($GPMBASE/gpm/bin/calc_optimum_pointing.py --metafits "${metafits}")
chgcentre \
          "${obsnum}.ms" \
          ${coords}
submodel="${obsnum}.ateam_outlier"
```
If submodel does not exist:
```
generate_ateam_subtract_model.py "${obsnum}.metafits" \
                                    --mode wsclean \
                                    --min-elevation 0.0 \
                                    --min-flux 5  \
                                    --check-fov \
                                    $debugoption \
                                    --model-output "${submodel}"
```
