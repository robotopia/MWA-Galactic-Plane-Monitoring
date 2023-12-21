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
## image
WSClean suffixes for subchannels and MFS
```
subchans="MFS 0000 0001 0002 0003"
```
Minimum uvw for self-calibration (in lambda)
```
minuv=75
```
S/N Level at which to choose masked pixels for deepclean
```
msigma=5
```
S/N Threshold at which to stop cleaning
```
tsigma=3
```
Set up telescope-configuration-dependent options
```
telescope="MWALB"
    basescale=0.6
    imsize=8000
    robust=0.5
```
Set up channel-dependent options
```
chan="$(pyhead.py -p CENTCHAN ${metafits} | awk '{print $3}')"
bandwidth="$(pyhead.py -p BANDWDTH ${metafits} | awk '{print $3}')"
centfreq="$(pyhead.py -p FREQCENT ${metafits} | awk '{print $3}')"
chans="$(pyhead.py -p CHANNELS ${metafits} | awk '{print $3}' | sed 's/,/ /g')"
chans=($chans)
```
Pixel scale: At least 4 pix per synth beam for each channel
```
scale=$(echo "$basescale / $chan" | bc -l)
```
Naming convention for output files
```
lowfreq=$(echo "${centfreq}" "${bandwidth}" | awk '{printf("%00d\n",$1-($2/2.)+0.5)}')
highfreq=$(echo "$centfreq $bandwidth" | awk '{printf("%00d\n",$1+($2/2.)+0.5)}')
freqrange="${lowfreq}-${highfreq}"
```
Calculate min uvw in metres
```
minuvm=$(echo "234 * $minuv / $chan" | bc -l)
```
Found that multiscale cleaning recovers flux dnesity in the extragalactic sky better than not, and doesn't add much to processing time
```
multiscale="-multiscale -mgain 0.85 -multiscale-gain 0.15"
```
Check whether the phase centre has already changed
```
current=$(chgcentre "${obsnum}.ms")
```
Determine whether to shift the pointing centre to be more optimally-centred on the peak of the primary beam sensitivity
```
coords=$(calc_pointing.py "${metafits}")
chgcentre \
            "${obsnum}.ms" \
            ${coords}
```
Now shift the pointing centre to point straight up, which approximates minw without making the phase centre rattle around
```
chgcentre \
            -zenith \
            -shiftback \
            "${obsnum}.ms"
```
Create a template image that has all the same properties as our eventual WSClean image
```
wsclean \
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
Set the pipefail so the test_fail does not test for tee
```
set -o pipefail
```
Deep clean (for pipeline)
```
wsclean \
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
Outputs have the generic format: {name}-t{ts:04d}-{chan:04d}-{pol}-image.fits
