from helios.app import Context, Next
from helios.auth.authenticator import Authenticator
from helios.http import Request, Response

from .config import Config
from .limiter import RateLimiter


class Middleware:
	"""Limits signed-out visitors' requests, keyed by a request header's value.

	Signed-in users and requests without the header are never limited. The
	header must be one that a trusted proxy sets, such as the client's address,
	because a client can send any value or leave the header out.
	"""

	def __init__(self, config: Config):
		self.header = config.header
		self.limiter = RateLimiter(config.limit, config.window)

	def __call__(self, request: Request, context: Context, next: Next) -> Response:
		auth = context.get(Authenticator)
		if not auth.is_signed_in() and self.header in request.headers:
			self.limiter.hit(str(request.headers[self.header]))
		return next(request, context)
