# cleepmod-cleepbus [![Coverage Status](https://coveralls.io/repos/github/tangb/cleepmod-cleepbus/badge.svg?branch=master)](https://coveralls.io/github/tangb/cleepmod-cleepbus?branch=master)

Cleepbus allows Cleep devices to communicate each other.

It is based on the great [0MQ](https://zeromq.org/) open source messaging library.

## Why 0MQ ?

Unlike other solutions that use MQTT solution for IoT communication, Cleep needs a network without a critical central point like the MQTT broker.

Thanks to a specific 0MQ implementation, Cleep implements a [mesh network](https://en.wikipedia.org/wiki/Mesh_networking).

One of Cleep requirement was to use the same way of communication between devices and desktop application used to configure devices. Using a broker would have required its installation on final user computer while 0MQ is directly embedded in Cleep software.

Of course it doesn't mean MQTT is not supported in Cleep. A specific application will be available to allow communication with other market devices that use MQTT.
