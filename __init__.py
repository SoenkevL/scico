import sys
from pathlib import Path

# Add source directory to path
source_dir = Path(__file__).parent  # adjust path as needed
if str(source_dir.resolve()) not in sys.path:
    sys.path.insert(0, str(source_dir.resolve()))
