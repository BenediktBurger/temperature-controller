# CHANGELOG

## [1.2.0] - 2024-01-16

_For upgrading, install *qtpy* first._


### Changed

- Use *qtpy* as dependency instead of testing for *PyQt5* and *PyQt6*.

### Added

- Add LECO (Laboratory Experiment Control prOtocol) functionality (optionally as it is not available on pypi yet).
- Add logging.
- Store the last output value (#6, #7).
- Add installation script controllerData/Setup.sh ([`c1a39734b`](https://git.rwth-aachen.de/nloqo/temperature-controller/-/commit/c1a39734b299add346c1fd684eddbdc319faddf9), [`3cf7c4512`](https://git.rwth-aachen.de/nloqo/temperature-controller/-/commit/3cf7c4512024f4029be5b1e14806e42d77bbc449)).
- Add possibility to read the last sensor value.


## [1.1.0] - 2021-07-21

### Changed

- Local sensor configuration is in controllerData/sensors.py. An example is in sensors-sample.py. Only "timestamp", "pidoutput0", "pidoutput1" are necessary columns in the database.

### Added

- Tests added for many functions and many cases of the TemperatureController and its files
- Sample code and explanation for installation via systemd included.
- Errors can be read and cleared via intercom (instead of being printed).

## Fixed

- Many bug fixes and stability improvements (error handling).


## [1.0.0] - 2021-06-18

_Initial release_
