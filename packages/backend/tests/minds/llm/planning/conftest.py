"""상위 폴더의 `llm_fakes`를 이 폴더 테스트에서도 import할 수 있게 한다."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
