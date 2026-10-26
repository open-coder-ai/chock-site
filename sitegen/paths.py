"""One rule for a path a data file names: it stays inside the folder it was named for."""

from pathlib import Path, PurePosixPath, PureWindowsPath

from .pageparts import PageError


def safe_join(root: Path, relative: object, what: str = "path") -> Path:
    """`root / relative`, refused unless it resolves to a path strictly inside `root`.

    An absolute path, a `..` segment, an empty name, or a symlink that leads out of
    the root fails the build naming the value. `what` names the value in the message.
    """
    if not isinstance(relative, str) or not relative:
        raise PageError(f"{what} {relative!r} is not a non-empty relative path")
    if PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).is_absolute():
        raise PageError(f"{what} {relative!r} is absolute; it must stay under {root}")
    if ".." in PurePosixPath(relative).parts or ".." in PureWindowsPath(relative).parts:
        raise PageError(f"{what} {relative!r} has a '..' segment")
    base = root.resolve()
    target = (root / relative).resolve()
    if target == base or not target.is_relative_to(base):
        raise PageError(f"{what} {relative!r} does not stay under {root}")
    return target
