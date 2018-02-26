# Cyclone auth digest example

This is a port of https://github.com/bkjones/curtain (Apache License)

## Basic usage

### import digest.py at the top of your views file

	import digest

### subclass digest.DigestAuthMixin in authenticated views

	class MainHandler(digest.DigestAuthMixin, cyclone.web.RequestHandler):

### define a password store. This function is expected to return a hash containing 
auth\_username and auth\_password.

    def passwordz(username):
        creds = {
                'auth_username': 'test',
                'auth_password': 'foobar'
                }
        if username == creds['auth_username']:
            return creds

### decorate views (get/post) with digest.digest_auth. Passing in authentication realm and password store. 
If authenticated, `self.current_user` will be properly set.

    @digest.digest_auth('Cyclone', passwordz)
    def get(self):
        self.write("Hello %s" % (self.current_user))
