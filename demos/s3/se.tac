#!/usr/bin/env python
# coding: utf-8
# twistd -ny s3.tac
# gleicon moraes (http://zenmachine.wordpress.com | http://github.com/gleicon)

SERVER_PORT = 4000

import s3server
from twisted.application import service, internet

application = service.Application("s3")
srv = internet.TCPServer(SERVER_PORT, s3server.S3Application(root_directory="/tmp/s3"))
srv.setServiceParent(application)

