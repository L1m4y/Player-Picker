# Changelog

## [1.4.0-1] - 2026-11-03

### Added
- Shared configuration, IPC, slot bookkeeping, axis scaling and test modules
- Daemon and GUI command-line options
- GitHub Actions CI workflow
- Arch packaging files
- Expanded README and architecture documentation

### Changed
- The GUI follows the slot count reported by the daemon
- IPC runs on a background thread
- The daemon resets slots on disconnect, reassignment and dropped synchronization
- Absolute axes are scaled between different source ranges
- Absolute event capability declaration now matches evdev's expected tuple format
- Virtual devices use the new entry-point console scripts

### Fixed
- Removed the duplicate SYN_REPORT emitted after every forwarded frame
- Fixed the hard-coded four-slot limit in the GUI
- Rejected invalid slot counts with a clear error
- Fixed the unused Qt style property that never produced opacity

### Security
- Validated that stale socket paths are real sockets before removing them
EOF
echo ok