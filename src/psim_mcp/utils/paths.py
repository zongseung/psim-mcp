"""Path security and validation utilities."""

from __future__ import annotations

from pathlib import Path

# Default set of file extensions allowed for PSIM project files.
_DEFAULT_ALLOWED_EXTENSIONS: set[str] = {".psimsch"}


def resolve_safe_path(path: str) -> str:
    """Normalise and resolve a filesystem path, following symlinks.

    Parameters
    ----------
    path:
        Raw path string (absolute or relative).

    Returns
    -------
    str
        Fully resolved absolute path.
    """
    return str(Path(path).resolve())


def is_path_allowed(file_path: str, allowed_dirs: list[str]) -> bool:
    """Check whether *file_path* falls under one of the *allowed_dirs*.

    Parameters
    ----------
    file_path:
        The path to validate.
    allowed_dirs:
        Whitelist of permitted directory roots.  If the list is **empty**
        (dev / unrestricted mode), every path is considered allowed.

    Returns
    -------
    bool
    """
    if not allowed_dirs:
        return True  # dev mode -- no restrictions

    resolved = Path(file_path).resolve()
    for allowed in allowed_dirs:
        allowed_resolved = Path(allowed).resolve()
        try:
            resolved.relative_to(allowed_resolved)
            return True
        except ValueError:
            continue
    return False


def validate_file_extension(
    filename: str,
    allowed_extensions: set[str] | None = None,
) -> bool:
    """Verify that *filename* has an allowed extension.

    Parameters
    ----------
    filename:
        File name or full path to check.
    allowed_extensions:
        Set of acceptable extensions **including the leading dot**
        (e.g. ``{".psimsch"}``).  Defaults to ``{".psimsch"}``.

    Returns
    -------
    bool
        ``True`` if the file's extension matches (case-insensitive).
    """
    if allowed_extensions is None:
        allowed_extensions = _DEFAULT_ALLOWED_EXTENSIONS

    ext = Path(filename).suffix.lower()
    return ext in {e.lower() for e in allowed_extensions}
