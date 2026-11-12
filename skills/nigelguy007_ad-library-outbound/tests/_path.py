"""Put the skill's scripts folder on sys.path for the tests."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "ad-library-outbound" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
