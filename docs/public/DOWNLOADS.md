# Downloads

These are the packaged artifacts currently committed in this repository for direct download.

## Windows

- `server/dist/windows/WebAgentBridgeSetup.exe`
  - normal end-user installer
- `server/dist/windows/WebAgentBridge.exe`
  - desktop companion app binary
- `server/dist/windows/webagent_protocol_built_exe.reg`
  - manual Windows protocol-registration fallback

Important:

- the current Windows binaries are unsigned
- Windows SmartScreen or Smart App Control may warn or block them
- for public end-user distribution, signed release binaries are still the preferred path

## Python package

- `server/dist/local_agent_bridge-0.1.0-py3-none-any.whl`
- `server/dist/local_agent_bridge-0.1.0.tar.gz`

These are useful for:

- local pip install
- internal mirrors
- manual testing without PyPI

## Widget package

- `widget/webagent-widget-0.1.0.tgz`

This is the packed npm tarball for `@webagent/widget`.

Install from the tarball:

```bash
npm install ./webagent-widget-0.1.0.tgz
```

## Checksums

- `server/dist/SHA256SUMS.txt`
- `widget/SHA256SUMS.txt`

## Notes

- Windows binaries are included directly in the repo right now so people can install immediately from GitHub.
- macOS and Linux still have source-based install flows documented in the repo.
- Linux/macOS native packaged binaries should ideally move to GitHub Releases later instead of staying in the source tree.
