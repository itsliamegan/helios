from helios.app import Context, Next
from helios.auth.state import Authenticator
from helios.http import Request, Response

from .config import Config
from .limiter import RateLimiter


class Middleware:
	def __init__(self, config: Config):
		self.header = config.header
		self.limiter = RateLimiter(config.limit, config.window)

	def __call__(self, request: Request, context: Context, next: Next) -> Response:
		auth = context.get(Authenticator)
		if not auth.is_signed_in() and self.header in request.headers:
			self.limiter.hit(str(request.headers[self.header]))
		return next(request, context)
