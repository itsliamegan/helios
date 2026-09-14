from helios.app import Context, Next
from helios.auth.state import Authenticator
from helios.http import Request, Response

from .config import Config
from .limiter import RateLimiter


class Middleware:
	def __init__(self, config: Config):
		self.header = config.header
		self.limiter = RateLimiter(config.limit, config.window)

	def __call__(self, req: Request, ctx: Context, next: Next) -> Response:
		auth = ctx.get(Authenticator)
		if not auth.is_signed_in() and self.header in req.headers:
			self.limiter.hit(str(req.headers[self.header]))
		return next(req, ctx)
