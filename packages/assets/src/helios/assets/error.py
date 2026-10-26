class CompileError(RuntimeError):
	"""Raised when esbuild fails or a script imports a stylesheet."""


class EntryNotFoundError(LookupError):
	"""Raised when a template includes an asset that the manifest lacks."""


class BundlerNotFoundError(LookupError):
	"""Raised when esbuild is not installed in the project."""


class ManifestNotFoundError(LookupError):
	"""Raised when the assets have not been compiled."""
