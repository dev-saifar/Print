import json
import asyncio
from snmp_printer_monitoring import discover_network_printers, SNMPPrinterMonitor
from app.models import Printer


def test_discover_printers(monkeypatch):
    responses = {
        '192.168.1.9': None,
        '192.168.1.10': {
            '1.3.6.1.2.1.1.5.0': 'Printer-10',
            '1.3.6.1.2.1.1.1.0': 'HP LaserJet',
            '1.3.6.1.2.1.43.5.1.1.17.1': 'SN123'
        }
    }

    from snmp_printer_monitoring import PRINTER_SNMP_OIDS

    async def fake_get(self, ip, community, oid):
        data = responses.get(ip, {})
        if oid == PRINTER_SNMP_OIDS['printer_status']:
            return 3
        return data.get(oid)

    monkeypatch.setattr(SNMPPrinterMonitor, '_snmp_get', fake_get)
    printers = asyncio.run(discover_network_printers('192.168.1.8/30'))
    assert printers == [{
        'ip': '192.168.1.10',
        'name': 'Printer-10',
        'model': 'HP LaserJet',
        'serial_number': 'SN123',
        'status': 'idle',
        'location': 'Unknown'
    }]


def test_discover_route_adds_printers(admin_client, monkeypatch):
    data = {
        '192.168.1.10': {
            '1.3.6.1.2.1.1.1.0': 'Canon Printer',
            '1.3.6.1.2.1.43.5.1.1.17.1': 'SN999'
        }
    }

    from snmp_printer_monitoring import PRINTER_SNMP_OIDS

    async def fake_get(self, ip, community, oid):
        vals = data.get(ip, {})
        if oid == PRINTER_SNMP_OIDS['printer_status']:
            return 3
        return vals.get(oid)

    monkeypatch.setattr(SNMPPrinterMonitor, '_snmp_get', fake_get)
    resp = admin_client.get('/admin/printers/discover?subnet=192.168.1.8/30')
    result = json.loads(resp.data)
    assert len(result['printers']) == 1

    # Post to create
    post_resp = admin_client.post('/admin/printers/discover', json={'printers': result['printers']})
    assert post_resp.json['success']

    printers = Printer.query.all()
    assert len(printers) == 1
    assert printers[0].ip_address == '192.168.1.10'
