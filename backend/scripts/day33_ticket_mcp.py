"""Private Day 33 stdio launcher; no file path is accepted from the caller."""
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from app.support_assistant.ticket_mcp_server import create_server

if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    create_server().run(transport='stdio')
