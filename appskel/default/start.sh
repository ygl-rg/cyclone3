#!/bin/bash
# see scripts/debian-init.d for production deployments

export PYTHONPATH=`dirname $$0`
twistd -n cyclone -p 8888 -l 0.0.0.0 \
       -r $modname.web.Application -c $modname.conf $$*
