"""Verifiers plugin entry point, loaded lazily so the checker also works on Windows."""

__all__ = ["MathematicsTaskset", "MathematicsEnv"]
__version__ = "0.2.0"


def __getattr__(name):
    if name in __all__:
        try:
            from . import taskset
        except ModuleNotFoundError as error:
            if error.name == "fcntl":
                raise RuntimeError(
                    "Verifiers 0.4 requires POSIX; run the environment in WSL/Linux. "
                    "The standalone checker works on Windows."
                ) from error
            raise
        return getattr(taskset, name)
    raise AttributeError(name)
