from cyclone import escape
from cyclone import httpclient
from cyclone.auth import OAuth2Mixin
from twisted.python import log

import urllib


class GitHubMixin(OAuth2Mixin):
    _OAUTH_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    _OAUTH_ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'

    def get_authenticated_user(self, redirect_uri, client_id, client_secret,
                               code, callback, extra_fields=None):

        args = {
            "redirect_uri": redirect_uri,
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret
        }

        fields = set(['access_token', 'token_type'])
        if extra_fields:
            fields.update(extra_fields)

        httpclient.fetch(self._oauth_request_token_url(**args))\
            .addCallback(self.async_callback(
                self._on_access_token, redirect_uri, client_id,
                client_secret, callback, fields))

    def _on_access_token(self, redirect_uri, client_id, client_secret,
                         callback, fields, response):

        if response.error:
            log.warning('GitHub auth error: %s' % str(response))
            callback(None)
            return

        args = escape.parse_qs_bytes(escape.native_str(response.body))
        session = {
            "access_token": args["access_token"][-1],
            "token_type": args["token_type"][-1],
        }

        self.github_request(
            path="/user",
            callback=self.async_callback(
                self._on_get_user_info, callback, session, fields),
            access_token=session["access_token"],
            fields=",".join(fields)
        )

    def _on_get_user_info(self, callback, session, fields, response):
        if response is None:
            callback(None)
            return
        fieldmap = {}
        args = escape.parse_qs_bytes(escape.native_str(response.body))
        for field in fields:
            fieldmap[field] = args.get(field, None)

        fieldmap.update({"access_token": session["access_token"],
                         "token_type": session.get("token_type")})
        callback(fieldmap)

    def github_request(self, path, callback, access_token=None,
                       post_args=None, **args):

        url = "https://api.github.com" + path

        all_args = {}
        if access_token:
            all_args["access_token"] = access_token
            all_args.update(args)

        if all_args:
            url += "?" + urllib.urlencode(all_args)
        cb = self.async_callback(self._on_gh_request, callback)
        if post_args is not None:
            httpclient.fetch(url, method="POST",
                             body=urllib.urlencode(post_args)).addCallback(cb)
        else:
            httpclient.fetch(url).addCallback(callback)

    def _on_gh_request(self, callback, response):
        if response.error:
            log.warning("Error response %s fetching %s", response.error,
                        response.request.url)
            callback(None)
            return
        callback(escape.json_decode(response.body))
