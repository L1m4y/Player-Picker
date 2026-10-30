# Player Picker Architecture

Player Picker uses one Linux daemon and one Qt interface.

The daemon creates the configured number of virtual Xbox 360 controllers with `evdev`. It grabs access to physical input devices and copies their events to the assigned virtual slot. Slot assignments are changed through a Unix socket using JSON messages.

The GUI polls the daemon twice per second and displays one card per slot. A click selects a source controller, and a second click moves it to the target slot. Moving a controller swaps the previous occupant back to the source slot.

Socket messages use the `get_state` and `set_slot` actions. The socket path and controller count can be changed through environment variables.
