### GitHub auth demo

Implements an oauth2 mixin for github.
Inspiration from fbgraphdemo and
http://casbon.me/connecting-to-githubs-oauth2-api-with-tornado.

To test the demo app that lists the description of all your gists:

[Register new app](github_auth/register_new_app.png)

Change github_client_id and github_secret with the respective values after
you register the new app.

$ python github_auth_example.py

[Authorize your login](github_auth/auth_screen.png)
