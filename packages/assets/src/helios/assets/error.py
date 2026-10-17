class CompileError(RuntimeError):
	pass


class EntryNotFoundError(LookupError):
	pass


class BundlerNotFoundError(LookupError):
	pass


class ManifestNotFoundError(LookupError):
	pass
