# Release-readiness acceptance checklist

Use this checklist on the latest local project, not just on an older source archive. Save screenshots of the successful transfer and relevant test output if this is for a project demonstration.

## Automated checks

- [ ] `python -m pytest -q` passes.
- [ ] `python -m compileall -q src` passes.
- [ ] `python -m ruff check src tests` passes (install development dependencies first if Ruff is missing).

## Manual transfer checks

- [ ] Small file transfers successfully from one GUI instance to another.
- [ ] Larger file transfers successfully and progress reaches 100%.
- [ ] Received file has the same SHA-256 hash as the source.
- [ ] Empty-file behavior is verified and documented.
- [ ] A destination filename collision is rejected; the existing file remains unchanged.
- [ ] Stopping the receiver during a transfer produces a useful failure message and the GUI remains responsive.
- [ ] An unavailable port produces a clear error rather than falsely showing that the receiver is listening.
- [ ] Sender and receiver logs make it possible to diagnose a failed START/ACK handshake.

## History checks

- [ ] A completed send appears in Recent Transfers.
- [ ] A completed receive appears in Recent Transfers.
- [ ] A failed transfer is recorded as failed rather than completed.
- [ ] History remains after closing and reopening the application.
- [ ] Search, status filtering, details, and CSV export behave correctly.
- [ ] If two instances run under the same Windows user, confirm that neither process silently erases the other's saved history when each records new transfers.

## Demonstration readiness

- [ ] Both application instances use the same receiver UDP port.
- [ ] Receiver is listening before sender starts.
- [ ] Test files and output folder are easy to locate.
- [ ] Old failed test rows are understood as historical attempts; filter history before taking final presentation screenshots if appropriate.
- [ ] README and run instructions match the current code.
