"""
tests/test_network/test_policy_engine.py
Unit tests for declarative network policy evaluation and CIDR boundary enforcement.
"""
from sovereign.config.settings import DEFAULT_POLICY_PATH
from sovereign.network.policy import NetworkPolicyEngine


def test_loopback_allowed():
    """Verify loopback IPv4 and IPv6 destinations are unconditionally allowed."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)

    verdict, reason = engine.evaluate_connection("127.0.0.1", 8080)
    assert verdict == "ALLOW"
    assert reason == "loopback_allowed"

    verdict, reason = engine.evaluate_connection("127.0.1.5", 9000)
    assert verdict == "ALLOW"
    assert reason == "loopback_allowed"

    verdict, reason = engine.evaluate_connection("::1", 8080)
    assert verdict == "ALLOW"
    assert reason == "loopback_allowed"


def test_listening_socket_allowed():
    """Verify unestablished/listening local sockets are allowed."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)

    verdict, reason = engine.evaluate_connection("", 0)
    assert verdict == "ALLOW"
    assert reason == "local_listening"

    verdict, reason = engine.evaluate_connection(None, 8000)
    assert verdict == "ALLOW"
    assert reason == "local_listening"


def test_intranet_subnets_allowed():
    """Verify configured enterprise intranet subnets are permitted."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)

    # 10.0.0.0/8
    verdict, reason = engine.evaluate_connection("10.50.1.12", 5432)
    assert verdict == "ALLOW"
    assert reason == "intranet_allowed"

    # 172.16.0.0/12
    verdict, reason = engine.evaluate_connection("172.20.10.5", 8080)
    assert verdict == "ALLOW"
    assert reason == "intranet_allowed"

    # 192.168.0.0/16
    verdict, reason = engine.evaluate_connection("192.168.1.254", 443)
    assert verdict == "ALLOW"
    assert reason == "intranet_allowed"


def test_denied_ports_strictly_blocked():
    """Verify denied ports (e.g. port 53 DNS) are rejected regardless of destination IP."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)

    # Port 53 on loopback
    verdict, reason = engine.evaluate_connection("127.0.0.1", 53)
    assert verdict == "DENY"
    assert reason == "port_53_strictly_denied"

    # Port 53 on intranet
    verdict, reason = engine.evaluate_connection("10.0.0.1", 53)
    assert verdict == "DENY"
    assert reason == "port_53_strictly_denied"

    # Port 53 on public DNS
    verdict, reason = engine.evaluate_connection("8.8.8.8", 53)
    assert verdict == "DENY"
    assert reason == "port_53_strictly_denied"


def test_public_internet_egress_denied():
    """Verify all external public internet IPs are blocked by default-deny rule."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)

    # Public IPv4 (Cloudflare, Google, AWS, Azure)
    for public_ip in ["1.1.1.1", "8.8.4.4", "52.95.110.1", "20.112.52.29"]:
        verdict, reason = engine.evaluate_connection(public_ip, 443)
        assert verdict == "DENY", f"Failed for {public_ip}"
        assert reason == "public_egress_default_deny"

    # Public IPv6 (Google DNS)
    verdict, reason = engine.evaluate_connection("2001:4860:4860::8888", 443)
    assert verdict == "DENY"
    assert reason == "public_egress_default_deny"


def test_invalid_ip_format():
    """Verify malformed or unresolvable IP strings are denied safely."""
    engine = NetworkPolicyEngine(DEFAULT_POLICY_PATH)

    verdict, reason = engine.evaluate_connection("not_an_ip", 80)
    assert verdict == "DENY"
    assert reason == "invalid_ip_format"

    verdict, reason = engine.evaluate_connection("999.999.999.999", 80)
    assert verdict == "DENY"
    assert reason == "invalid_ip_format"
