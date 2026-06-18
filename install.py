import subprocess
import sys

print("Скачиваем c104...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "c104"])
print("Готово! Библиотека c104 установлена.")
