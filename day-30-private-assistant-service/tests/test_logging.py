"""Exercise real Uvicorn logging setup in an isolated, offline process."""
from pathlib import Path
import subprocess
import sys


def test_launcher_suppresses_transport_logs_after_uvicorn_configuration():
    script = r'''
import logging
import sys
import httpx
import uvicorn
import server
import laa_service.config as configuration
import laa_service.app as application

configuration.load_config = lambda _: object()
application.create_app = lambda _: object()

def configure_and_probe(app, **kwargs):
    # This is the logging reconfiguration performed inside uvicorn.run.
    assert kwargs['log_config'] is None
    uvicorn.Config(app, **kwargs)
    assert not logging.getLogger('httpx').disabled
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        client.get('http://127.0.0.1/PRIVATE_PATH?key=PRIVATE_QUERY',
                   headers={'Authorization': 'Bearer PRIVATE_HEADER'})
    # Descendants may be created after startup. Neither DEBUG nor ERROR may
    # escape to root handlers or logging.lastResort, including exception text.
    for name in ('httpx', 'httpx.new_child', 'httpcore', 'httpcore.connection', 'uvicorn.access'):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        logger.debug('PRIVATE_BODY PRIVATE_SOURCE')
        try:
            raise ValueError('PRIVATE_EXCEPTION')
        except ValueError:
            logger.exception('PRIVATE_URL PRIVATE_TOKEN')
    logging.getLogger('laa.http').info('operation_finished request_id=safe active=0 recovery=False')
    logging.getLogger('laa.http').info('http_finished request_id=safe route=health status=200 elapsed_ms=1')

uvicorn.run = configure_and_probe
sys.argv = ['server.py', '--config', 'unused-local-config']
assert server.main() == 0
'''
    result = subprocess.run([sys.executable, '-B', '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    output = result.stdout + result.stderr
    assert 'PRIVATE' not in output
    assert 'HTTP Request:' not in output
    assert 'operation_finished request_id=safe active=0 recovery=False' in output
    assert 'route=health status=200 elapsed_ms=1' in output
