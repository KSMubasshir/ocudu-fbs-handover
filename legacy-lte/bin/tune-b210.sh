#!/bin/bash

set -x

( sudo uhd_find_devices && sudo uhd_usrp_probe ) \
    || ( echo "ERROR: cannot find radio" && exit 1 )
