from distutils.core import setup
from glob import glob

reqs = [
    "astropy",
    "numpy",
    "scipy",
    "matplotlib",
    "mwa_pb_lookup",
    "calplots",
    "casacore",
    "healpy",
    "requests",
    "mysqlconnector",
    "psutil",
]

scripts = glob('gpm/bin/*.py') + glob('gpm/db/*.py') + glob('gpm/utils/*.py')

setup(
    name="gpm",
    version="0.1",
    author="Natasha Hurley-Walker, Paul Hancock, Tim Galvin",
    description="Python scripts to support the processing of Galactic Plane Monitoring data.",
    url="https://github.com/robotopia/MWA-Galactic-Plane-Monitoring",
    long_description=open("README.md").read(),
    packages=["gpm", "gpm.bin", "gpm.db", "gpm.utils"],
    requires=reqs,
    scripts=scripts,
)
