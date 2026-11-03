# Player Picker architecture

Player Picker uses one daemon and one Qt interface.

## Daemon

`playerpicker.daemon` creates the configured number of virtual Xbox 360 controllers through the
Linux `uinput` interface. Physical devices are accepted when they expose gamepad buttons and are
not keyboards or Player Picker virtual devices. The daemon grabs each one and forwards its events
to the assigned slot. Moves swap the moved controller and the previous occupant atomically.
The affected slot is reset when a controller is moved, disconnected or dropped.

## Forwarding

- Buttons are forwarded only when declared by the virtual device.
- Absolute axes are scaled into the virtual Xbox 360 range.
- `SYN_REPORT` ends a frame; `SYN_DROPPED` resets the affected slot.
- `EV_MSC` events are not forwarded.

## GUI

The GUI polls the daemon twice per second over a Unix socket. Its slot count follows the daemon,
so no hard-coded tile limit exists. It hides to the tray when a tray is available.

## IPC

Requests are newline-terminated JSON objects:

- `get_state` -> `{"status": "ok", "slots": N, "version": "...", "devices": [
  {"path": ..., "name": ..., "slot": ...}]}`
- `set_slot` -> `{"path": ..., "slot": ...}` -> `{"status": "ok", "slot": ...}`

Errors return `{"status": "error", "error": "..."}`.

## Configuration

`PLAYER_PICKER_SOCKET` selects the socket, `PLAYER_PICKER_SLOTS` the number of virtual slots and
`PLAYER_PICKER_ICONS` an alternative icon directory. The command-line options `--socket`,
`--slots`, `--log-level` and `--version` also exist.

## Security

The socket is world-writable so an unprivileged GUI can reach the root daemon. In practice this
means every local process can perform the operations that the GUI performs.
EOF
echo ok