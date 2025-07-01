import asyncio
import ipaddress
from typing import List, Dict

SYS_DESCR_OID = '1.3.6.1.2.1.1.1.0'
SERIAL_OID = '1.3.6.1.2.1.43.5.1.1.17.1'


def _snmp_get(ip: str, oid: str, community: str = 'public') -> str | None:
    """Perform a simple SNMP GET operation."""
    try:
        from pysnmp.hlapi.v1arch.asyncio import CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity, cmdgen
        from pysnmp.entity.engine import SnmpEngine

        async def run() -> str | None:
            errorIndication, errorStatus, errorIndex, varBinds = await cmdgen.get_cmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((ip, 161), timeout=1, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            if errorIndication or errorStatus:
                return None
            return str(varBinds[0][1])

        return asyncio.get_event_loop().run_until_complete(run())
    except Exception:
        return None


def discover_printers(subnet: str) -> List[Dict[str, str]]:
    """Scan the given subnet for network printers using SNMP."""
    printers: List[Dict[str, str]] = []
    network = ipaddress.ip_network(subnet, strict=False)
    for ip in network.hosts():
        ip_str = str(ip)
        descr = _snmp_get(ip_str, SYS_DESCR_OID)
        if not descr:
            continue
        model = descr.split()[0]
        serial = _snmp_get(ip_str, SERIAL_OID) or ''
        printers.append({'ip': ip_str, 'model': model, 'serial_number': serial})
    return printers
