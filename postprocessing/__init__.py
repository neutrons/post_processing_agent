# postprocessing version - from package metadata
from importlib import metadata

__version__ = metadata.version("postprocessing")
del metadata