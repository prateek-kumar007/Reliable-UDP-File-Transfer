# Reliable UDP File Transfer — Windows Quick Start

**Version:** v0.1.0  
**Platform:** Windows 64-bit  
**Recommended for friends:** Download the ready-to-run ZIP. You do **not** need to install Python or Git.

## Project links

- **[Download the Windows app (.zip)](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer/releases/download/v0.1.0/ReliableUDPFileTransfer-Windows-x64.zip)**
- [Release page and other downloads](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer/releases/tag/v0.1.0)
- [GitHub source code](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer)
- [Full Windows user manual](USER_MANUAL.md)
- [Acceptance test results](docs/ACCEPTANCE_TEST_RESULTS.md)

## 1. Download and open the app

1. Download the Windows ZIP from the link above.
2. In File Explorer, right-click the ZIP and choose **Extract All**.
3. Open the extracted folder.
4. Double-click **ReliableUDPFileTransfer.exe**.

**Keep the whole extracted folder together.** Do not run the EXE from inside the ZIP or move the EXE by itself.

## 2. Try a transfer on one computer

You need two app windows: one receives the file and the other sends it.

1. Open the app twice so you have two windows.
2. In the first window, select **Receive files**.
3. Choose a destination folder. For your first test, use a new empty folder.
4. Set the port to **5001** and click **Start listening**.
5. In the second window, select **Send a file** and choose a small test file.
6. Set **Peer IP** to `127.0.0.1` and the port to **5001**.
7. Click **Start transfer**.
8. Wait for the sender to show **Completed** and the receiver to show **Completed — integrity verified**.

That's the basic test. The sender and receiver should both report completion.

### Important: files are not overwritten

If a file with the same name already exists in the receiver's destination folder, the app refuses to overwrite it. Choose a new destination folder or move/rename the existing file before trying again.

## 3. Send a file to a friend's laptop

This is for two laptops on the **same trusted Wi-Fi/network**.

1. On your friend's receiving laptop, open the app, choose **Receive files**, select a destination folder, set port **5001**, and click **Start listening**.
2. On that receiving laptop, open PowerShell and run:
   ```powershell
   ipconfig
   ```
3. Find the **IPv4 Address** under the active Wi-Fi or Ethernet adapter. It may look like `192.168.1.25`.
4. On the receiving laptop, allow the app or UDP port **5001** through Windows Defender Firewall for the **Private** network profile if the firewall blocks the transfer.
5. On the sending laptop, open the app, choose **Send a file**, pick the file, enter the receiver's IPv4 address as **Peer IP**, and use port **5001**.
6. Start the transfer after the receiver is listening.

For a different laptop, **do not use `127.0.0.1`**. That address means “this same computer.” Use the receiver laptop's IPv4 address instead.

## 4. Common problems

- **Transfer fails or keeps retrying:** Start the receiver first, confirm it is listening, and check the sender's IP address and port.
- **Port error 10048 / cannot listen:** Another app is using that port. Stop the other receiver or choose another available port on the receiver and use the same port on the sender.
- **File already exists:** Choose a destination folder that does not already contain a file with the incoming filename.
- **Two laptops cannot connect:** Confirm both are on a network that allows device-to-device traffic and check the receiver's firewall settings.

## 5. More help

Read the [full Windows User Manual](USER_MANUAL.md) for interface details, transfer history, SHA-256 verification, laptop-to-laptop setup, and troubleshooting. The project source and issue tracking are available in the [GitHub repository](https://github.com/prateek-kumar007/Reliable-UDP-File-Transfer).

**Network note:** The transfer protocol does not encrypt files or authenticate peers. Use it on a trusted network and do not send sensitive files over an untrusted network.
