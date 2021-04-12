#!/bin/sh

# install libs
python3 -m pip install --trusted-host pypi.org "pyre-gevent==0.2.3" "pyzmq==22.0.3"
if [ $? -ne 0 ]; then
    exit 1
fi

