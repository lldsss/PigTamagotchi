"""Точка входа для панели BotHost; стандартный запуск — python -m pig_tamagotchi."""

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    runpy.run_module("pig_tamagotchi", run_name="__main__")
