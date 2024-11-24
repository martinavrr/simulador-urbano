#!/usr/bin/env bash

set -e

cd "data/external"
mkdir OSM
cd OSM

wget -nc https://download.geofabrik.de/south-america/chile-latest.osm.pbf
wget -nc -O "rm.poly" "http://polygons.openstreetmap.fr/get_poly.py?id=198848&params=0.004000-0.001000-0.001000"

osmconvert chile-latest.osm.pbf -B=rm.poly --out-pbf -o=chile-rm-latest.osm.pbf

cd "../../.."