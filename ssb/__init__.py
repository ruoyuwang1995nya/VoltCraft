import os
__version__ = '0.0.1'
LOCAL_PATH = os.getcwd()


def header():
    header_str = ""
    header_str += f"==>> Solid State Battery simulations (v{__version__})\n"
    header_str += "Checking input files..."
    print(header_str)