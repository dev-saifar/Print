import json
from app.printer_discovery import discover_printers
from app.models import Printer


def test_discover_printers(monkeypatch):
    responses = {
        '192.168.1.9': None,
        '192.168.1.10': {
            '1.3.6.1.2.1.1.1.0': 'HP LaserJet',
            '1.3.6.1.2.1.43.5.1.1.17.1': 'SN123'
        }
    }

    def fake_get(ip, oid, community='public'):
        data = responses.get(ip, {})
        if data:
            return data.get(oid)
        return None

    monkeypatch.setattr('app.printer_discovery._snmp_get', fake_get)
    printers = discover_printers('192.168.1.8/30')
    assert printers == [{'ip': '192.168.1.10', 'model': 'HP', 'serial_number': 'SN123'}]


def test_discover_route_adds_printers(admin_client, monkeypatch):
    data = {
        '192.168.1.10': {
            '1.3.6.1.2.1.1.1.0': 'Canon Printer',
            '1.3.6.1.2.1.43.5.1.1.17.1': 'SN999'
        }
    }

    def fake_get(ip, oid, community='public'):
        vals = data.get(ip, {})
        return vals.get(oid)

    monkeypatch.setattr('app.printer_discovery._snmp_get', fake_get)
    resp = admin_client.get('/admin/printers/discover?subnet=192.168.1.8/30')
    result = json.loads(resp.data)
    assert len(result['printers']) == 1

    # Post to create
    post_resp = admin_client.post('/admin/printers/discover', json={'printers': result['printers']})
    assert post_resp.json['success']

    printers = Printer.query.all()
    assert len(printers) == 1
    assert printers[0].ip_address == '192.168.1.10'
