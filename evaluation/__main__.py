import sys

from app.transport import MissingSecret
from evaluation import main
from evaluation._live import live_llm

try:
    sys.exit(main(sys.argv[1:], llm=live_llm))
except MissingSecret as error:
    sys.exit(f"{error}. Export the key first (see evaluation/README.md); nothing was sent.")
