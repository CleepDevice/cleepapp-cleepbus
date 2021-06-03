#!/bin/sh

# install libs
python3 -m pip install --trusted-host pypi.org "pyre-gevent==0.2.3" "pyzmq==22.1.0" "greenlet==1.0.0" "gevent==21.1.2"
if [ $? -ne 0 ]; then
    exit 1
fi

