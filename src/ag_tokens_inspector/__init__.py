from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__package__ or __name__)
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
