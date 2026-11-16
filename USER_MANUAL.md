# Windows User Manual

This guide explains how to install, launch, and use Reliable UDP File Transfer on Windows. It is written for teammates who want to run the application, try the five acceptance scenarios, and understand what the interface reports.

## Choose how to run it

**Packaged Windows build (recommended for ordinary users):** when a versioned Windows ZIP is published, download it from the repository's [Releases page](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer/releases), extract the whole ZIP to a normal folder, and launch `ReliableUDPFileTransfer.exe`. Do not move the executable by itself; keep the bundled support files beside it.

**Run from source (available now):** follow the installation steps below. Python 3.12+ and a Python installation with Tkinter are required.

## 1. Install and launch from source

1. Install Git and Python 3.12 or newer. On Windows, choose a Python build that includes Tcl/Tk.
2. Open PowerShell and run:

```powershell
git clone https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer.git
cd Reliable-UDP-File-Transfer
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m reliable_udp.gui.app
```

3. To open a second application instance, open another PowerShell window, navigate to the same repository folder, activate `.venv`, and run `python -m reliable_udp.gui.app` again.

If PowerShell blocks activation, run the virtual environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m reliable_udp.gui.app
```

The project has no third-party runtime dependencies. The `[dev]` extra installs pytest and Ruff for developers.

## 2. Send a file between two instances on one laptop

1. Open two application windows.
2. In one window, select **Receive files**.
3. Choose a destination folder that does not already contain a file with the incoming filename.
4. Set UDP port to `5001`, then click **Start listening**. Wait for the status to say `Listening on UDP 5001`.
5. In the second window, select **Send a file** and browse to the source file.
6. Set peer IP to `127.0.0.1` and UDP port to `5001`. For the first test, keep the default chunk size, timeout, and retry settings.
7. Click **Start transfer**. Wait for the sender to say `Completed` and the receiver to say `Completed — integrity verified`.
8. Check that the file exists in the receiver's save folder.

**Important:** the receiver deliberately refuses to overwrite an existing destination file. Use a new empty folder for normal transfers. The overwrite-protection test is the intentional exception.

## 3. Transfer between two laptops on the same network

1. Connect both laptops to the same trusted local network.
2. On the receiving laptop, open the app, select **Receive files**, choose a destination folder, and start listening on a UDP port such as `5001`.
3. On the receiving laptop, open PowerShell and run `ipconfig`. Find the IPv4 address of the active Wi-Fi or Ethernet adapter (for example, `192.168.1.25`). Do not use `127.0.0.1` for another laptop; that address refers to the local machine.
4. On the receiving laptop, allow the application or UDP port through Windows Defender Firewall **for the appropriate Private network profile only** if Windows prompts you or blocks the transfer.
5. On the sending laptop, open the application, select **Send a file**, select a source file, enter the receiver laptop's IPv4 address, and enter the same UDP port.
6. Start the transfer after the receiver is listening.

Both devices must be reachable over UDP. Transfers across different networks may require router, VPN, or NAT configuration and are not the first setup to try.

## 4. Understand the interface

- **Transfer:** choose Send or Receive; set file, destination, IP, port, chunk size, timeout, and retries; watch progress and activity events.
- **Logs:** inspect application events and troubleshooting information.
- **Recent Transfers:** review completed and failed transfers, search/filter records, inspect a record, and export CSV.
- **Settings:** adjust persistent defaults.
- **About:** see application information.

The receiver's `Completed — integrity verified` status means it validated the declared size and SHA-256 digest before publishing the received file. For an independent check, compare the source and received file hashes with PowerShell:

```powershell
Get-FileHash "C:\path\to\source-file" -Algorithm SHA256
Get-FileHash "C:\path\to\received-file" -Algorithm SHA256
```

The two hash values should match.

## 5. Where history is stored

Transfer history is saved to:

```text
%USERPROFILE%\.reliable_udp\transfer_history.json
```

It loads when the application starts and retains up to 1,000 records. The JSON file is useful for diagnostics; do not edit it while the application is running. A backup can be made by closing the app and copying the file.

## 6. Common problems

### "Could not listen on UDP port" / Windows error 10048

Another program is already using that local port. Stop the other receiver or choose a free port. If two instances are running on the same laptop, only one receiver can bind a given address/port combination at a time.

### Sender retries START and then fails

- Confirm the receiver is currently listening.
- Confirm the sender's peer IP and UDP port match the receiver.
- On one laptop, use `127.0.0.1`; between laptops, use the receiving laptop's active IPv4 address.
- Use a destination folder that does not already contain the source filename. This application rejects overwrite attempts and may not ACK a START request if storage cannot be initialized.
- Check Windows firewall and network reachability for cross-laptop transfers.

### Sender or receiver does not update / appears frozen

Wait briefly for the current transfer to finish. For a large transfer, save the Activity logs and note the file size, chunk count, and sender/receiver statuses. Do not report a large transfer as passed until the sender completes and an independent SHA-256 comparison succeeds.

### The application doesn't launch

For source runs, verify that Python 3.12+ and Tkinter are installed, the virtual environment is activated, and the repository was installed with `python -m pip install -e ".[dev]"`. For a packaged run, extract the entire ZIP and launch the EXE from the extracted folder.

## 7. Run project checks (developers)

From the repository root, after activating the virtual environment:

```powershell
python -m pytest -q
python -m compileall -q src
python -m ruff check src tests
```

A recorded source snapshot passed 107 tests, Python compilation, and Ruff. Re-run these commands against the version you're using.

## 8. Test scenarios for a report

Use the procedure and actual results in [Acceptance Test Results](docs/ACCEPTANCE_TEST_RESULTS.md). Screenshots are stored in [docs/screenshots](docs/screenshots). Keep the evidence for each test separate and report incomplete checks as incomplete rather than passed.
