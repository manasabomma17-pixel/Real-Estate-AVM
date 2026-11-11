# makes "import backend" and "import data_processing" work when pytest runs
# from the project folder
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
