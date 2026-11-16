# Reliable UDP File Transfer

A Python desktop application for transferring files over UDP with a custom **Stop-and-Wait ARQ** reliability layer. It adds acknowledgements, timeout-based retransmissions, transfer identifiers, sequence numbers, and SHA-256 verification on top of UDP.

## Features

- **Stop-and-Wait ARQ:** Sends one data chunk at a time and waits for its acknowledgement before advancing.
- **Timeouts and retransmissions:** Retries a transfer packet when its matching acknowledgement is not received within the configured timeout.
- **Transfer identity and sequencing:** Uses a transfer ID and sequence number to match protocol messages to the active transfer.
- **Integrity verification:** Checks the declared file size and SHA-256 digest before publishing a received file.
- **No-overwrite storage:** Received files are written to a temporary file and published only after verification. An existing destination file is never overwritten.
- **Tkinter desktop GUI:** Sender and receiver controls in the transfer dashboard, including progress, elapsed time, packet attempts, and transfer rate.
- **Activity logs:** Displays protocol and transfer events in the GUI.
- **Transfer history:** Tracks completed and failed transfers, provides filtering and CSV export, and persists history between application restarts.
- **Automated tests:** Includes unit and integration tests for packet encoding, metadata validation, transport behavior, receiver behavior, and file transfers.

## Technology stack

- Python 3.12 or newer
- Tkinter (desktop GUI)
- UDP sockets
- Stop-and-Wait ARQ
- SHA-256 (`hashlib`)
- pytest (tests)
- Ruff (linting)

The application has no third-party runtime dependencies. `pytest` and `ruff` are development dependencies.

## Requirements

- Python 3.12+
- Tkinter support in the Python installation
- Git, if cloning the repository

On Windows, use a Python installation that includes Tcl/Tk. The commands below use PowerShell.

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer.git
cd Reliable-UDP-File-Transfer
```

### 2. Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the virtual environment's Python executable directly, for example `\.venv\Scripts\python.exe`.

### 3. Install the project and development tools

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4. Launch the GUI

```powershell
python -m reliable_udp.gui.app
```

## Run a local transfer

To transfer a file between two application instances on the same computer:

1. Launch the application in two separate windows by running `python -m reliable_udp.gui.app` twice.
2. In the first window, select **Receive files**, choose an existing destination folder, set the UDP port (the default is `5001`), and click **Start listening**.
3. In the second window, select **Send a file**, choose a source file, set the peer IP to `127.0.0.1`, and enter the same UDP port as the receiver.
4. Click **Start transfer** and wait for the sender and receiver to report completion.
5. Confirm that the receiver reports successful integrity verification and that the received file matches the source.

The receiver binds to all local IPv4 interfaces on the selected port. The sender's peer IP and port must identify the receiver. If the port is already occupied, stop the application using it or choose another available port on both sides.

### Important: existing destination files

The receiver **does not overwrite existing files**. If the destination folder already contains a file with the incoming filename, choose another destination folder or move the existing file before retrying. This protects existing data.

## Transfer between different computers

Both computers must have network reachability over UDP. Start the receiver first, then configure the sender with the receiver computer's reachable IP address and listening port. Allow the selected UDP port through the receiver's firewall. Transfers across separate networks may require router or network configuration.

## Transfer protocol overview

1. The sender creates metadata containing the filename, file size, chunk size, and SHA-256 digest, then sends a `START` packet.
2. The receiver validates the request and replies with an acknowledgement when it accepts the transfer.
3. The sender transmits `DATA` chunks sequentially and waits for the matching acknowledgement. Packets are retried after timeout when necessary.
4. The sender sends `END` after all chunks have been acknowledged; the receiver verifies the received byte count and SHA-256 digest before publishing the file.
5. The receiver sends `FIN_ACK` after successful finalization.

Packets use a fixed header containing a protocol marker, message type, transfer ID, sequence number, and payload length. The maximum UDP datagram size configured by the project is 1,200 bytes, including the 27-byte header; the maximum data payload is 1,173 bytes.

## Transfer history

The GUI saves transfer history in JSON format at:

```text
%USERPROFILE%\.reliable_udp\transfer_history.json
```

On startup, the application loads saved history. The application retains up to 1,000 history entries. Activity logs are intended for the current application session; transfer history is the persistent record.

## Tests and linting

Run the complete test suite from the repository root:

```powershell
python -m pytest -q
```

Compile the Python source files:

```powershell
python -m compileall -q src
```

Run Ruff:

```powershell
python -m python -m ruff check src tests
```

The project snapshot reviewed for this README passed **107 tests** and Python compilation. Re-run the commands above after making code changes to verify your working copy.

## User guide, acceptance tests, and distribution

- [Windows User Manual](USER_MANUAL.md): install from source, run sender/receiver, transfer between laptops, understand history, and troubleshoot errors.
- [Manual Acceptance Test Results](docs/ACCEPTANCE_TEST_RESULTS.md): observed results for small/large transfers, overwrite protection, port conflict, and persistent history.
- [Release-readiness checklist](RELEASE_CHECKLIST.md): additional manual checks before calling a release ready.
- [GitHub Releases](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer/releases): download the packaged Windows build when a versioned release is published.

A Windows packaging workflow is available under `.github/workflows/build-windows.yml`. Run it from the repository's **Actions** tab to produce a short-lived test artifact. Publishing a version tag such as `v0.2.0` runs the same tests and attaches the Windows ZIP to a GitHub Release. The packaged build has not been called release-ready until it is tested on a separate laptop.

**Manual-test caveat:** AT-04 currently proves that an occupied UDP port is reported (Windows error 10048); confirming that the second GUI remains responsive after dismissing the dialog is still pending. See the acceptance report for this exact status.

## Project structure

```text
Reliable-UDP-File-Transfer/
├── src/
│   └── reliable_udp/
│       ├── gui/
│       │   ├── app.py
│       │   ├── components.py
│       │   ├── transfer_page.py
│       │   ├── logs_page.py
│       │   ├── history_page.py
│       │   ├── settings_page.py
│       │   └── about_page.py
│       ├── file_storage.py
│       ├── metadata.py
│       ├── protocol.py
│       ├── receiver.py
│       ├── receiver_service.py
│       ├── sender.py
│       └── transport.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── acceptance/
├── pyproject.toml
└── README.md
```

## Limitations

- Stop-and-Wait ARQ sends one data chunk at a time, so throughput may be limited on high-latency networks.
- Reliability mechanisms do not provide encryption or peer authentication. Do not treat the protocol as a secure channel for sensitive files on untrusted networks.
- Transfers depend on network reachability, correct addresses and ports, and firewall configuration.
- The receiver intentionally refuses to overwrite files already present at the destination.

## Author

**Prateek Kumar Singh**

- GitHub: [@prateek-kumar007](https://github.com/prateek-kumar007)
- Repository: [Reliable UDP File Transfer](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer)
