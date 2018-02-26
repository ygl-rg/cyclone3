import cyclone.web
import cyclone.auth
from cyclone import escape, httpclient
from twisted.internet import task, defer

try:
    import urllib.parse as urllib_parse  # py3
except ImportError:
    import urllib as urllib_parse  # py2


class DropboxMixin(cyclone.auth.OAuth2Mixin):
    """Dropbox authentication using OAuth2.

    https://www.dropbox.com/developers/core/docs

    """
    _OAUTH_AUTHORIZE_URL = "https://www.dropbox.com/1/oauth2/authorize"
    _OAUTH_ACCESS_TOKEN_URL = "https://api.dropbox.com/1/oauth2/token"
    _OAUTH_SETTINGS_KEY = 'dropbox_oauth'

    @property
    def oauth_settings(self):
        return self.settings[self._OAUTH_SETTINGS_KEY]

    @defer.inlineCallbacks
    def get_authenticated_user(self, code):
        """Handles the login for the Dropbox user, returning a user object."""
        body = urllib_parse.urlencode({
            "redirect_uri": self.oauth_settings["redirect"],
            "code": code,
            "client_id": self.oauth_settings['key'],
            "client_secret": self.oauth_settings['secret'],
            "grant_type": "authorization_code",
        })
        print body

        response = yield cyclone.httpclient.fetch(
            self._OAUTH_ACCESS_TOKEN_URL,
            method="POST",
            headers={'Content-Type': ['application/x-www-form-urlencoded']},
            postdata=body
        )

        if response.error:
            msg = 'Dropbox auth error: {}'.format(str(response))
            cyclone.auth.AuthError(msg)
            defer.returnValue(None)

        args = escape.json_decode(response.body)
        defer.returnValue(args)

    def authorize_redirect(self):
        kwargs = {
            "redirect_uri": self.oauth_settings["redirect"],
            "client_id": self.oauth_settings["key"],
            "extra_params": {"response_type": "code"}
        }

        return super(DropboxMixin, self).authorize_redirect(**kwargs)

