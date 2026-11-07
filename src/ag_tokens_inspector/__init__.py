from importlib.metadata import PackageNotFoundError, metadata, version

try:
    __version__ = version(__package__ or __name__)
    __app_name__ = metadata(__package__ or __name__)["Name"]
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
    __version__ = "0.0.0+unknown"
    __app_name__ = (__package__ or __name__).replace("_", "-")

__all__ = ["__app_name__", "__version__"]
