import io
import os
import re

from setuptools import find_packages, setup

# Get some values from the setup.cfg
try:
    from ConfigParser import ConfigParser
except ImportError:
    from configparser import ConfigParser

conf = ConfigParser()
conf.read(["setup.cfg"])
metadata = dict(conf.items("metadata"))


def read(filename):
    filename = os.path.join(os.path.dirname(__file__), filename)
    text_type = type(u"")
    with io.open(filename, mode="r", encoding="utf-8") as fd:
        return re.sub(text_type(r":[a-z]+:`~?(.*?)`"), text_type(r"``\1``"), fd.read())


# Metadata
exec(open("src/zorzim/version.py", encoding="utf8").read())

PACKAGENAME = metadata.get("package_name", "zorzim")
URL = metadata.get("url", "https://github.com/Gresh1234/zorzim")
LICENSE = metadata.get("license", "GPL3")
AUTHOR = metadata.get("author_name", "Elías Moreno-Vergara")
AUTHOR_EMAIL = metadata.get("author_email", "elmoreno@dcc.uchile.cl")
DESCRIPTION = metadata.get(
    "description",
    "(data Zcience)-ORiented ZImulation of Mobility.",
)


setup(
    name=PACKAGENAME,
    version=__version__,
    url=URL,
    license=LICENSE,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    description=DESCRIPTION,
    long_description=read("README.md"),
    packages=find_packages(where="src", exclude=("tests",)),
    package_dir={"": "src"},
    install_requires=[],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
    ],
)
