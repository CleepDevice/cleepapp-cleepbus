#!/bin/sh

# install libs
python3 -m pip install https://github.com/CleepDevice/cleep-libs-prebuild/raw/main/pyzmq/pyzmq-22.3.0-cp37-cp37m-linux_armv7l.whl
python3 -m pip install --trusted-host pypi.org "pyre-gevent==0.2.3"
if [ $? -ne 0 ]; then
    exit 1
fi

