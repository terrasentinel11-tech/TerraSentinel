"""Allowlisted TCP client for explicitly configured laboratory endpoints."""
from __future__ import annotations

import ipaddress
import json
import socket
import time


def validate_lab_endpoint(host: str, port: int, allow_hosts: set[str]) -> None:
    if host not in allow_hosts:
        raise ValueError(f"host {host!r} is not in the explicit allowlist")
    if not 1 <= int(port) <= 65535:
        raise ValueError("invalid TCP port")
    addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not (ip.is_loopback or ip.is_private):
            raise ValueError(f"refusing non-private address {address}")


def transmit(data: bytes, *, host: str, port: int, allow_hosts: set[str],
             timeout_s: float = 10.0, delay_s: float = 0.0,
             close_after: int | None = None) -> dict:
    validate_lab_endpoint(host, port, allow_hosts)
    started = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout_s) as conn:
        conn.settimeout(timeout_s)
        outgoing = data if close_after is None else data[:close_after]
        if delay_s:
            time.sleep(min(float(delay_s), timeout_s))
        conn.sendall(outgoing)
        if close_after is not None:
            conn.shutdown(socket.SHUT_WR)
        reply = bytearray()
        while b"\n" not in reply:
            part = conn.recv(65536)
            if not part:
                break
            reply.extend(part)
            if len(reply) > 1024 * 1024:
                raise ValueError("receiver response exceeds 1 MiB")
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    if not reply:
        return {"status": "connection_closed", "latency_ms": elapsed_ms}
    result = json.loads(reply.split(b"\n", 1)[0])
    result["client_latency_ms"] = elapsed_ms
    return result

