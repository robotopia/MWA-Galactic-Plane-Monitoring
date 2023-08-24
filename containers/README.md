# Singularity build recipes for tooling related to Galactic Plane Monitoring

Build with:
```
sudo singularity build gpm_tools.img gpm_build.txt
```

By default, the above uses `/tmp` as a sandbox directory while creating the image.
If `/tmp` exists on a partition where there is not enough space, the build may fail.
This may be fixed by setting the `SINGULARITY_TMPDIR` environment variable to a location that exists on a larger partition, and exporting that to the build command.
For example:
```
export SINGULARITY_TMPDIR=$HOME/tmp
sudo -E singularity build gpm_tools.img gpm_build.txt
```

Once built the container has all software packages required to process GPM data. 

External data dependencies related to the MWA primary beam are not packed within the container. Doing so would increase the container filesize considerably. 

The container include the 'mwa-reduce' software package, which is only available to the MWA collaboration. 
