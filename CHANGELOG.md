# Changelog

## [Unreleased]

### Added
- Refresh the peer `auth` header from inventory so desktop sees live HTTP basic-auth state (same cadence as `remoteaccess`)

### Changed
- Replace `postinst.sh` with declarative `scripts/postinst.json`
- Map core peer device info (`_get_peer_device_info`) to ZRE headers in the app; inventory stays in `CleepExternalBus`
- Apply changes to new test stack (pylint)

## [2.3.4] - 2026-10-16

### Added
- Advertise registered public addresses in the peer announcement (`remoteaccess`), and refresh that header so the next peer receives the current one

## [2.3.3] - 2026-10-12

### Fixed
- Auto-restart external bus when ZRE discovery dies (`$TERM` / empty node message) so devices stay visible after long uptime or network flaps
- Restart discovery on `network.status.update` when the device IP changes
- Require pyre-gevent 1.0.0 (beacon no longer suicides on transient UDP send errors)

### Changed
- Drop `str2bool` dependency; parse peer header bools with a local `_as_bool` helper

### Added
- Config page: Pyre connection status, peers list, and last 20 bus activity entries
  (`get_bus_status`) for on-device debugging
- Log outbound propagated events (broadcast) in the activity buffer

## [2.3.2] - 2026-10-12

### Changed
- Shorten ZRE poll timeout (50ms) so internal bus is not starved by `_on_process`
- Execute inbound peer commands asynchronously (task_factory) instead of blocking the module loop
- Reduce `get_modules` timeout when building peer infos at bus start
- Validate `_send_event_to_peer` parameters like commands (peer exists / online)

### Fixed
- Correct `auth` field documentation in `get_peer_infos`

## [2.3.1] - 2024-11-01

### Changed
- Update pyre-gevent lib to 0.3.1

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

