from helios.database import Model
from helios.wsgi.test import TestClient

from .authenticator import SESSION_KEY


def sign_in(client: TestClient, user: Model):
	"""Sign a user in for the client's next requests."""

	with client.session() as session:
		session[SESSION_KEY] = str(user.id)
