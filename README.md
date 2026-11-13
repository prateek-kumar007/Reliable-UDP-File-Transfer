\# Reliable UDP File Transfer



A Python desktop application for reliable file transfer over UDP using the \*\*Stop-and-Wait ARQ\*\* protocol.



The project demonstrates how reliability can be built on top of UDP using acknowledgements, retransmissions, transfer progress tracking, and file-integrity verification.



\## Features



\- \*\*Stop-and-Wait ARQ:\*\* Sends data chunks and waits for acknowledgements.

\- \*\*Reliable transfer:\*\* Supports retransmission when acknowledgements are not received as expected.

\- \*\*File-integrity verification:\*\* Verifies the received file using its size and SHA-256 hash.

\- \*\*Desktop GUI:\*\* Built with Python Tkinter.

\- \*\*Transfer monitoring:\*\* Displays progress, elapsed time, transfer statistics, and status.

\- \*\*Additional pages:\*\* Logs, recent transfers, settings, and application information.

\- \*\*Automated tests:\*\* Unit, integration, and acceptance tests.



\## Technology Stack



\- Python 3.12+

\- Tkinter

\- UDP sockets

\- Stop-and-Wait ARQ

\- SHA-256

\- pytest

\- Ruff



\## Requirements



\- Python 3.12 or newer

\- Git

\- Tkinter support in your Python installation



No third-party runtime packages are declared in the project configuration. `pytest` and `ruff` are used for development and testing.



\## Getting Started



\### 1. Clone the repository



```bash

git clone https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer.git

cd Reliable-UDP-File-Transfer

```



\### 2. Create a virtual environment



\*\*Windows PowerShell\*\*



```powershell

py -3.12 -m venv .venv

.\\.venv\\Scripts\\Activate.ps1

```



If PowerShell blocks activation, you can run the environment's Python directly using `.venv\\Scripts\\python.exe`.



\### 3. Install development dependencies



```powershell

python -m pip install -e ".\[dev]"

```



\### 4. Launch the desktop application



```powershell

python -m reliable\_udp.gui.app

```



If the package is not installed in editable mode, run it with the project source path configured as described in the project setup.



\## How to Use



1\. Launch the application.

2\. Open the \*\*Receiver\*\* interface and choose a destination folder and UDP port.

3\. Start listening on the receiver.

4\. Open the sender interface or a second application instance.

5\. Select the file to send and enter the receiver's IP address and port.

6\. Start the transfer.

7\. Wait for the sender and receiver to report completion.

8\. Confirm that the receiver reports successful integrity verification.



\### Local testing



To test two application instances on the same computer, use:



\- Receiver address: `0.0.0.0`

\- Receiver port: `5001`

\- Sender destination IP: `127.0.0.1`

\- Sender destination port: `5001`



Ensure the receiver is listening before starting the sender. Use a different available port if port `5001` is already occupied.



\### Transfer between different computers



Both computers must be able to communicate over UDP. Use the receiver computer's reachable IP address, configure the required firewall rules, and ensure the selected UDP port is allowed. Devices on separate networks may require additional network configuration.



\## Run the Tests



Run the full test suite:



```powershell

python -m pytest -q

```



Run Ruff:



```powershell

ruff check src\\reliable\_udp

```



\## Project Structure



```text

Reliable-UDP-File-Transfer/

├── src/

│   └── reliable\_udp/

│       ├── gui/

│       │   ├── app.py

│       │   ├── transfer\_page.py

│       │   ├── logs\_page.py

│       │   ├── history\_page.py

│       │   ├── settings\_page.py

│       │   └── about\_page.py

│       ├── file\_storage.py

│       ├── metadata.py

│       ├── protocol.py

│       ├── receiver.py

│       ├── receiver\_service.py

│       ├── sender.py

│       └── transport.py

├── tests/

├── logs/

├── pyproject.toml

├── .gitignore

└── README.md

```



\## Current Test Status



The project test suite passed locally with \*\*107 tests passing\*\*. To verify the current version on your machine, run the test commands above.



\## Limitations



\- The current interface is a desktop application, not a hosted web application.

\- Transfers between computers depend on network reachability and firewall configuration.

\- The protocol is designed for reliable delivery, not encryption. Do not use it to transfer sensitive files over untrusted networks without adding appropriate security.



\## Author



\*\*Prateek Kumar Singh\*\*



GitHub: \[@prateek-kumar007](https://github.com/prateek-kumar007)



\## Repository



\[Reliable UDP File Transfer on GitHub](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer)
