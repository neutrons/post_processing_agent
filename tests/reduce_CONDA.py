CONDA_ENV = "sans-dev"
import sys
import drtsans

print(f"drtsans: {drtsans}")
print(f"command: {sys.argv[1:]}")
raise RuntimeError("Whatever")
