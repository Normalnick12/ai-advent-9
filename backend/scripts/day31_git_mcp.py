"""Private stdio server launcher, owned by the Day 31 client."""
import argparse
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from app.developer_assistant.git_mcp_server import create_server


if __name__ == '__main__':
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    args = parser.parse_args()
    create_server(args.repo).run(transport='stdio')
