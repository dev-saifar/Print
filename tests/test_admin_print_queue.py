from app.models import PrintQueue, db

def test_print_queue_page(admin_client, app):
    with app.app_context():
        job = PrintQueue(filename='testfile.pdf', user_ip='127.0.0.1')
        db.session.add(job)
        db.session.commit()
    resp = admin_client.get('/admin/print-queue')
    assert resp.status_code == 200
    assert b'testfile.pdf' in resp.data
