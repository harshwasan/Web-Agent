import sys

from webagent_server.bridge_runtime import append_runtime_log
from webagent_server.desktop_app import main as desktop_main
from webagent_server.server import main as bridge_main


if __name__ == "__main__":
    try:
        if "--bridge-server" in sys.argv[1:]:
            append_runtime_log("bridge_server.log", "Bridge server entry launched")
            bridge_main()
        else:
            desktop_main()
    except Exception as exc:
        target = "bridge_server.log" if "--bridge-server" in sys.argv[1:] else "desktop_app.log"
        append_runtime_log(target, "Fatal startup error: %s" % exc)
        raise
