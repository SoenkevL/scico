import logging
import sys

import coloredlogs

coloredlogs.install(level='INFO')
from pathlib import Path

logger = logging.getLogger(__name__)
# Add project root to Python path if not already present
project_root = Path(__file__).parent.parent.resolve()  # Go up one level to scico/
logging.info(f"Project root: {project_root}")
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
