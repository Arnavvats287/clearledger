"""Python capability guard plus OS resource limits for credential-isolated workers.

Not a substitute for a separate OS principal/container against dependency RCE.
"""

import ipaddress
import os
import socket
import sys
from pathlib import Path
from typing import Any


def posix_limits() -> None:
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def install_guard(*, allow_gemini: bool = False) -> None:
    roots = [Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve()]
    app = Path(__file__).resolve().parent
    certificates = [Path("/etc/ssl/certs"), Path("/etc/pki/tls/certs")]
    addresses: set[str] = set()
    original_resolve = socket.getaddrinfo
    host_name = "generativelanguage.googleapis.com"
    if allow_gemini:

        def resolve(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
            if host not in {host_name, host_name.encode()} or port not in {443, "443"}:
                raise PermissionError("GATEWAY_DESTINATION_DENIED")
            answers = original_resolve(host, port, *args, **kwargs)
            approved = [item for item in answers if ipaddress.ip_address(str(item[4][0])).is_global]
            addresses.update(str(item[4][0]) for item in approved)
            if not approved:
                raise PermissionError("GATEWAY_DESTINATION_DENIED")
            return approved

        socket.getaddrinfo = resolve

    def guard(event: str, arguments: tuple[Any, ...]) -> None:
        if event.startswith(("subprocess.", "os.system", "ctypes.dlopen")):
            raise PermissionError("WORKER_TOOL_DENIED")
        if event.startswith("socket."):
            if not allow_gemini:
                raise PermissionError("WORKER_NETWORK_DENIED")
            if event == "socket.getaddrinfo":
                if arguments[0] not in {host_name, host_name.encode()} or arguments[1] != 443:
                    raise PermissionError("GATEWAY_DESTINATION_DENIED")
            elif event == "socket.connect":
                address = arguments[1]
                if address[0] not in addresses or address[1] != 443:
                    raise PermissionError("GATEWAY_DESTINATION_DENIED")
            elif event == "socket.__new__":
                if (
                    arguments[1] not in {socket.AF_INET, socket.AF_INET6}
                    or arguments[2] != socket.SOCK_STREAM
                ):
                    raise PermissionError("GATEWAY_SOCKET_DENIED")
            else:
                raise PermissionError("GATEWAY_SOCKET_DENIED")
        if event == "open":
            path, mode = arguments[:2]
            if isinstance(path, int):
                return
            if not isinstance(path, (str, bytes)) or not isinstance(mode, str):
                raise PermissionError("WORKER_FILESYSTEM_DENIED")
            resolved = Path(os.fsdecode(path)).resolve()
            allowed = (
                not any(char in mode for char in "wax+")
                and not resolved.is_relative_to(app)
                and any(resolved.is_relative_to(root) for root in roots + certificates)
            )
            if not allowed:
                raise PermissionError("WORKER_FILESYSTEM_DENIED")

    sys.addaudithook(guard)
