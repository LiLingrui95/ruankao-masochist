"""Independent numerical checks for B07 examples and exercises."""
from decimal import Decimal
from ipaddress import ip_address, ip_network


def longest_prefix(address: str, routes: list[tuple[str, str]]) -> str:
    addr = ip_address(address)
    matches = [(ip_network(prefix).prefixlen, next_hop) for prefix, next_hop in routes if addr in ip_network(prefix)]
    return max(matches)[1]


def cumulative_ack(next_expected: int, segments: list[tuple[int, int]]) -> int:
    intervals = sorted((start, start + length) for start, length in segments)
    cursor = next_expected
    changed = True
    while changed:
        changed = False
        for start, end in intervals:
            if start <= cursor < end:
                cursor = end
                changed = True
    return cursor


def main() -> None:
    net = ip_network("172.16.35.77/20", strict=False)
    assert str(net) == "172.16.32.0/20"
    assert str(net.broadcast_address) == "172.16.47.255"
    assert net.num_addresses - 2 == 4094

    net23 = ip_network("10.3.14.9/23", strict=False)
    assert (str(net23.network_address), str(net23.broadcast_address)) == ("10.3.14.0", "10.3.15.255")
    vlsm = [ip_network(x) for x in ("192.168.10.0/26", "192.168.10.64/27", "192.168.10.96/28")]
    assert all(not a.overlaps(b) for i, a in enumerate(vlsm) for b in vlsm[i + 1 :])
    assert list(ip_network("192.168.4.0/22").subnets(new_prefix=24)) == [ip_network(f"192.168.{i}.0/24") for i in range(4, 8)]

    routes = [("10.0.0.0/8", "A"), ("10.1.0.0/16", "B"), ("10.1.2.0/24", "C"), ("0.0.0.0/0", "D")]
    assert longest_prefix("10.1.2.9", routes) == "C"
    assert longest_prefix("10.2.1.1", routes) == "A"
    assert longest_prefix("192.0.2.1", routes) == "D"

    assert cumulative_ack(1000, [(1200, 200)]) == 1000
    assert cumulative_ack(1000, [(1200, 200), (1000, 200)]) == 1400
    assert min(64, 40) - 24 == 16

    tx_ms = 1000 * 8 / 20_000_000 * 1000
    assert tx_ms == 0.4
    assert tx_ms + 10 == 10.4
    assert 100_000_000 * 0.04 == 4_000_000

    assert pow(3, -1, 40) == 27
    assert pow(pow(7, 3, 55), 27, 55) == 7

    value = Decimal("200")
    exposure = Decimal("0.25")
    aro_before = Decimal("0.2")
    aro_after = Decimal("0.05")
    cost = Decimal("4")
    sle = value * exposure
    before = sle * aro_before
    after = sle * aro_after
    assert (sle, before, after, before - after - cost) == (Decimal("50"), Decimal("10.0"), Decimal("2.50"), Decimal("3.50"))
    print("B07 numerical checks passed: CIDR/VLSM, routing, TCP ACK, delay/BDP, RSA, ALE")


if __name__ == "__main__":
    main()
