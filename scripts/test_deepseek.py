import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.deepseek import call_deepseek  # noqa: E402


async def main() -> None:
    reply, model = await call_deepseek("Reply with exactly: DEEPSEEK_API_OK")
    print(f"MODEL={model}")
    print(f"RESULT={reply}")


if __name__ == "__main__":
    asyncio.run(main())
