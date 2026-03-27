# Build Binaries

This package can be turned into a native-feeling desktop companion binary with PyInstaller.

## What gets built

- `WebAgentBridge`
  - starts the local bridge
  - supports the desktop UI
  - supports tray/background mode
  - can be used as the `webagent://` protocol target

## Windows

From `server/`:

```powershell
powershell -ExecutionPolicy Bypass -File .\build\build_windows.ps1
powershell -ExecutionPolicy Bypass -File .\build\build_windows_installer.ps1
```

Output:

- `server\dist\windows\WebAgentBridge.exe`
- `server\dist\windows\WebAgentBridgeInstaller.exe`

Protocol registration options:

- preferred for end users: run `WebAgentBridgeInstaller.exe`
- preferred: run `local-agent-bridge-install`
- fallback template: edit and import `server/installers/windows/webagent_protocol_template.reg`
- built-exe fallback: run `powershell -ExecutionPolicy Bypass -File .\build\write_windows_reg_for_built_exe.ps1`

## macOS

From `server/`:

```bash
chmod +x ./build/build_macos.sh
./build/build_macos.sh
```

Output:

- `server/dist/macos/WebAgentBridge.app` or equivalent PyInstaller output

Protocol registration:

- run `local-agent-bridge-install`

## Linux

From `server/`:

```bash
chmod +x ./build/build_linux.sh
./build/build_linux.sh
chmod +x ./build/build_linux_setup.sh
./build/build_linux_setup.sh
```

Output:

- `server/dist/linux/WebAgentBridge`
- `server/dist/linux/WebAgentBridgeSetup.tar.gz`

Protocol registration:

- run `local-agent-bridge-install`

Linux setup bundle contents:

- `WebAgentBridge`
- `installer_ui.sh`
- `install_webagent_bridge.sh`
- `uninstall_webagent_bridge.sh`

Typical Linux user flow:

```bash
tar -xzf WebAgentBridgeSetup.tar.gz
cd extracted-folder
./installer_ui.sh
```

## Tray mode

The desktop app supports background mode:

```bash
local-agent-bridge-app --tray
```

For built binaries, pass the same flag to `WebAgentBridge`.

## Notes

- Build on each target OS for best results.
- Tkinter must be available on the build machine.
- On Linux, system tray support depends on the desktop environment.
