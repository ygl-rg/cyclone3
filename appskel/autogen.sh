#!/bin/bash

set -e
cd `dirname $0`
for d in `find . -type d -depth 1 -exec basename {} \;`
do
  name="appskel_$d.zip"
  skel="../../cyclone/${name}"
  echo Generating ${name}...
  rm -f $skel
  cd $d
  zip -r $skel .
  cd ..
  echo done
done
