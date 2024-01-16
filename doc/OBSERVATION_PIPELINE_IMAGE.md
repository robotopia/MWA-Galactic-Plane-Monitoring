# Observation Pipeline: To image

## autoflag

The flags are obtained from the `gp_monitor` database,
```
flags=$(${GPMBASE}/gpm_track.py --obs_id ${obsnum} obs_flagantennae)
```

Then, they are applied to the measurement set:
```
flagantennae ${obsnum}.ms $flags
```

## apply_cal

Get the assigned calibration solution from the database (see [AUX_GETCAL.md](AUX_GETCAL.md)).

In production mode, apply to Data column:
```
 applysolutions \
                -nocopy \
                ${obsnum}.ms \
                "${calfile}"
```

## uvflag

Assuming production mode (i.e. using DATA column in measurement set):

```
ms_flag_by_uvdist.py "${obsnum}.ms" DATA -a
```

## uvsub

A template script to generate a model of a-team sources that will be subtracted from the visibility dataset.
The idea is to make small images around a-team sources which that than subtracted from the visibilities.
We are using wsclean to first chgcenter and the clean a small region arount the source.
This is then subtracted from the column DATA.

Reset the phase centre:
```
current=$(chgcentre "${obsnum}.ms")
coords=$($GPMBASE/gpm/bin/calc_optimum_pointing.py --metafits "${metafits}")
chgcentre \
          "${obsnum}.ms" \
          ${coords}
submodel="${obsnum}.ateam_outlier"
```

If submodel does not exist, make one:
```
generate_ateam_subtract_model.py "${obsnum}.metafits" \
                                    --mode wsclean \
                                    --min-elevation 0.0 \
                                    --min-flux 5  \
                                    --check-fov \
                                    $debugoption \
                                    --model-output "${submodel}"
```

## image

Variables:

| Variable | Description | Value |
| :------- | :---------- | :---- |
| subchans | WSClean suffixes for subchannels and MFS | "MFS 0000 0001 0002 0003" |
| minuv | Minimum uvw for self-calibration (in wavelengths) | 75 |
| msigma | S/N Level at which to choose masked pixels for deepclean | 3 |
| tsigma | S/N Threshold at which to stop cleaning | 1 |
| telescope | The MWA configuration | MWALB (= long baseline) |
| basescale | Per-frequency scaling (depends on array config) | 0.6 |
| imsize | Size of resulting image in pixels | 8000 |
| robust | Briggs weighting (depends on array config) | 0.5 |
| chan | Centre channel (receiver number) | (Depends on observation. for GPM, always 157) |
| scale | Pixel scale: At least 4 pix per synth beam for each channel | basescale / chan |
| minuvm | Minimum UVW in metres | 234 * minuv / chan |
| multiscale | Settings for better extragalactic sky flux density recovery | "-multiscale -mgain 0.85 -multiscale-gain 0.15" |

Optimum coords for image pointing are obtained:
```
coords=$($GPMBASE/gpm/bin/calc_optimum_pointing.py --metafits "${metafits}")
```

### Template image

| Variable | Description | Value |
| :------- | :---------- | :---- |
| [mgain] | | 1.0 |
| [nmiter] | | 1 |
| [niter] | | 0 |
| [channel-range] | | 4 5 |
| [interval] | | 4 5 |
| [pol] | | XX |


Create a template image that has all the same properties as our eventual WSClean image
```
wsclean \
            -gridder wgridder \
            -shift ${coord} \
            -abs-mem ${GPMMEMORY} \
            -mgain 1.0 \
            -nmiter 1 \
            -niter 0 \
            -name ${obsnum}_template \
            -size ${imsize} ${imsize} \
            -scale ${scale:0:8} \
            -pol XX \
            -data-column ${datacolumn} \
            -channel-range 4 5 \
            -interval 4 5 \
            -nwlayers ${GPMNCPUS} \
            "${obsnum}.ms"

rm "${obsnum}_template-dirty.fits"
mv "${obsnum}_template-image.fits" "${obsnum}_template.fits"
```

### Subband beams

Hardcoding John's PB script location for now. Also hardcoding creating four sub-band beams
```
pols="XX XXi XY XYi YX YXi YY YYi"

for n in {0..3}
do
    i=$((n * 6))
    cstart=${chans[$i]}
    j=$((i + 5))
    cend=${chans[$j]}
    for pol in $pols
    do
        if [[ ! -e "${obsnum}_000${n}-${pol}-beam.fits" ]]
        then
            lookup_jones.py ${obsnum} _template.fits ${obsnum}_000${n}- -c $cstart-$cend --wsclean_names
            if [[ $? != 0 ]]
            then
                echo "The script lookup_jones.py failed. Stopping now."
                exit 1
            fi
        fi
        ln -s "${obsnum}_000${n}-${pol}-beam.fits" "${obsnum}_deep-000${n}-beam-${pol}.fits"
    done
done
```

### Deep clean (for pipeline)

| Variable | Description | Value |
| :------- | :---------- | :---- |
| [nmiter] | | 5 |
| [niter] | | 10000000 |
| [channels-out] | | 4 |
| [fit-spectral-pol] | | 2 |
| [pol] | | I,Q,U,V |

```
wsclean \
        -gridder wgridder \
        -shift ${coord} \
        -abs-mem ${GPMMEMORY} \
        $multiscale \
        -nmiter 5 \
        -niter 10000000 \
        -reuse-primary-beam \
        -apply-primary-beam \
        -auto-mask ${msigma} \
        -auto-threshold ${tsigma} \
        -name ${obsnum}_deep \
        -size ${imsize} ${imsize} \
        -scale ${scale:0:8} \
        -weight briggs ${robust} \
        -pol I,Q,U,V \
        -join-channels \
        -channels-out 4 \
        -fit-spectral-pol 2 \
        -data-column ${datacolumn} \
        "${obsnum}.ms" | tee wsclean.log
```

Outputs have the generic format: `{name}-deep-{chan:04d}-{pol}-image.fits`
