import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

@pytest.fixture
def app(monkeypatch):
    from app import create_app
    # Prevent LPR server from starting
    monkeypatch.setattr('app.start_lpr_server', lambda app: None)
    # Prevent scheduler from running during tests
    monkeypatch.setattr('app.scheduler.start', lambda *a, **k: None)
    app = create_app()
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    client.post('/login', data={'username': 'admin', 'password': 'admin123'})
    return client
