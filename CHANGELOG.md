# Changelog

## [2.3.0] - 2024-03-17
### Changed
- Handle netifaces2 breaking changes

### Added
- Handle RPC config (https)
- Handle auth

## [2.2.4] - 2023-03-12
### Changed
- Improve code quality (lint+black)

## [2.2.3] - 2023-02-12
### Changed
- Postinst pyzmq from prebuild version available on cleep-libs-prebuild repo

## [2.2.2] - 2023-02-10
### Changed
- Install provided pyzmq library instead of pypi one

## [2.2.1] - 2023-02-08
### Changed
- Update pyzmq dep to cleep-pyzmq for build optimization (pre build armhf bin)

## [2.2.0] - 2022-01-25
### Changed
- Remove useless python dependencies (mandatory in core)

## [2.1.1] - 2021-07-09
### Changed
* Peer log message changed from info to debug
* Add message that was not sent when external bus is not available

## [2.1.0] - 2021-06-03

* Fix issue: peer ident not correctly saved
* Do not execute process on unknown peer
* Improve endpoint search reliability
* Fix issue when receiving whisper message
* Update pyzmq to 22.1.0 in postinst.sh to match with cleep 0.0.27

## [2.0.2] - 2021-04-13

* Fix build
* Improve code quality

## [2.0.1] - 2021-04-12

* Add postinst script
* Fix tests
* Improve code quality (lint)
* Add missing function send_event_to_peer

## [2.0.0] - 2020-12-13

* Migrate to Python3
* Update after core changes
* Clean and optimize code
* Add unit tests
* Implement external bus commands

## [1.1.1] - 2019-10-20

* Update after core changes

## [1.1.0] - 2019-09-30

* Update after core changes
* Return more infos about device

## [1.0.1] - 2018-10-14

* Fix small issues

## [1.0.0] - 2018-10-08

* First official release

