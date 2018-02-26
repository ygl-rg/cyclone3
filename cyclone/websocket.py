# coding: utf-8
#
# Copyright 2010 Alexandre Fiori
# based on the original Tornado by Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""Server-side implementation of the WebSocket protocol.

`WebSocket <http://en.wikipedia.org/wiki/WebSocket>`_  is a web technology
providing full-duplex communications channels over a single TCP connection.

For more information, check out the `WebSocket demos
<https://github.com/fiorix/cyclone/tree/master/demos/websocket>`_.
"""
import base64
import functools
import hashlib
import struct

import cyclone
import cyclone.web
import cyclone.escape

from twisted.python import log


class _NotEnoughFrame(Exception):
    pass


class WebSocketHandler(cyclone.web.RequestHandler):
    """Subclass this class to create a basic WebSocket handler.

    Override messageReceived to handle incoming messages.

    See http://dev.w3.org/html5/websockets/ for details on the
    JavaScript interface.  The protocol is specified at
    http://tools.ietf.org/html/rfc6455.

    Here is an example Web Socket handler that echos back all received messages
    back to the client::

      class EchoWebSocket(websocket.WebSocketHandler):
          def connectionMade(self):
              print "WebSocket connected"

          def messageReceived(self, message):
              self.sendMessage(u"You said: " + message)

          def connectionLost(self, reason):
              print "WebSocket disconnected"

    Web Sockets are not standard HTTP connections. The "handshake" is HTTP,
    but after the handshake, the protocol is message-based. Consequently,
    most of the Cyclone HTTP facilities are not available in handlers of this
    type. The only communication methods available to you is sendMessage().

    If you map the handler above to "/websocket" in your application, you can
    invoke it in JavaScript with::

      var ws = new WebSocket("ws://localhost:8888/websocket");
      ws.onopen = function() {
         ws.send("Hello, world");
      };
      ws.onmessage = function (evt) {
         alert(evt.data);
      };

    This script pops up an alert box that says "You said: Hello, world".
    """
    def __init__(self, application, request, **kwargs):
        cyclone.web.RequestHandler.__init__(self, application, request,
                                            **kwargs)
        self.application = application
        self.request = request
        self.transport = request.connection.transport
        self.ws_protocol = None
        self.notifyFinish().addCallback(self.connectionLost)

    def headersReceived(self):
        pass

    def connectionMade(self, *args, **kwargs):
        pass

    def connectionLost(self, reason):
        pass

    def messageReceived(self, message):
        """Gets called when a message is received from the peer."""
        pass

    def sendMessage(self, message):
        """Sends the given message to the client of this Web Socket.

        The message may be either a string or a dict (which will be
        encoded as json).
        """
        if isinstance(message, dict):
            message = cyclone.escape.json_encode(message)
        if isinstance(message, str):
            message = message.encode("utf-8")
        assert isinstance(message, str)
        self.ws_protocol.sendMessage(message)

    def _rawDataReceived(self, data):
        self.ws_protocol.handleRawData(data)

    def _execute(self, transforms, *args, **kwargs):
        self._transforms = transforms or list()
        try:
            assert self.request.headers["Upgrade"].lower() == "websocket"
        except:
            return self.forbidConnection("Expected WebSocket Headers")

        self._connectionMade = functools.partial(self.connectionMade,
                                                 *args, **kwargs)

        if "Sec-Websocket-Version" in self.request.headers and \
            self.request.headers['Sec-Websocket-Version'] in ('7', '8', '13'):
            self.ws_protocol = WebSocketProtocol17(self)
        elif "Sec-WebSocket-Version" in self.request.headers:
            self.transport.write(cyclone.escape.utf8(
                "HTTP/1.1 426 Upgrade Required\r\n"
                "Sec-WebSocket-Version: 8\r\n\r\n"))
            self.transport.loseConnection()
        else:
            self.ws_protocol = WebSocketProtocol76(self)

        self.request.connection.setRawMode()
        self.request.connection.rawDataReceived = \
            self.ws_protocol.rawDataReceived
        self.ws_protocol.acceptConnection()

    def forbidConnection(self, message):
        self.transport.write(
            "HTTP/1.1 403 Forbidden\r\nContent-Length: %s\r\n\r\n%s" %
            (str(len(message)), message))
        return self.transport.loseConnection()


class WebSocketProtocol(object):
    def __init__(self, handler):
        self.handler = handler
        self.request = handler.request
        self.transport = handler.transport

    def acceptConnection(self):
        pass

    def rawDataReceived(self, data):
        pass

    def sendMessage(self, message):
        pass


class WebSocketProtocol17(WebSocketProtocol):
    def __init__(self, handler):
        WebSocketProtocol.__init__(self, handler)

        self._partial_data = None

        self._frame_fin = None
        self._frame_rsv = None
        self._frame_ops = None
        self._frame_mask = None
        self._frame_payload_length = None
        self._frame_header_length = None

        self._data_len = None
        self._header_index = None

        self._message_buffer = ""

    def acceptConnection(self):
        log.msg('Using ws spec (draft 17)')

        # The difference between version 8 and 13 is that in 8 the
        # client sends a "Sec-Websocket-Origin" header and in 13 it's
        # simply "Origin".
        if 'Origin' in self.request.headers:
            origin = self.request.headers['Origin']
        else:
            origin = self.request.headers['Sec-Websocket-Origin']

        key = self.request.headers['Sec-Websocket-Key']
        accept = base64.b64encode(hashlib.sha1("%s%s" %
            (key, '258EAFA5-E914-47DA-95CA-C5AB0DC85B11')).digest())

        self.transport.write(
            "HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
            "Upgrade: WebSocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: %s\r\n"
            "Server: cyclone/%s\r\n"
            "WebSocket-Origin: %s\r\n"
            "WebSocket-Location: ws://%s%s\r\n\r\n" %
            (accept, cyclone.version, origin,
             self.request.host, self.request.path))

        self.handler._connectionMade()

    def rawDataReceived(self, data):
        while True:
            if self._partial_data:
                data = self._partial_data + data
                self._partial_data = None

            try:
                self._processFrameHeader(data)
            except _NotEnoughFrame:
                self._partial_data = data
                return

            self._message_buffer += self._extractMessageFromFrame(data)

            if self._frame_fin:
                if self._frame_ops == 8:
                    self.sendMessage(self._message_buffer, code=0x88)
                    #self.handler.connectionLost(self._message_buffer)
                elif self._frame_ops == 9:
                    self.sendMessage(self._message_buffer, code=0x8A)
                else:
                    self.handler.messageReceived(self._message_buffer)
                self._message_buffer = ""

            # if there is still data after this frame, process again
            current_len = self._frame_header_len + self._frame_payload_len
            if current_len < self._data_len:
                data = data[current_len:]
            else:
                break

    def _processFrameHeader(self, data):

        self._data_len = len(data)

        # we need at least 2 bytes to start processing a frame
        if self._data_len < 2:
            raise _NotEnoughFrame()

        # first byte contains fin, rsv and ops
        b = ord(data[0])
        self._frame_fin = (b & 0x80) != 0
        self._frame_rsv = (b & 0x70) >> 4
        self._frame_ops = b & 0x0f

        # second byte contains mask and payload length
        b = ord(data[1])
        self._frame_mask = (b & 0x80) != 0
        frame_payload_len1 = b & 0x7f

        # accumulating for self._frame_header_len
        i = 2

        if frame_payload_len1 < 126:
            self._frame_payload_len = frame_payload_len1
        elif frame_payload_len1 == 126:
            i += 2
            if self._data_len < i:
                raise _NotEnoughFrame()
            self._frame_payload_len = struct.unpack("!H", data[i - 2:i])[0]
        elif frame_payload_len1 == 127:
            i += 8
            if self._data_len < i:
                raise _NotEnoughFrame()
            self._frame_payload_len = struct.unpack("!Q", data[i - 8:i])[0]

        if (self._frame_mask):
            i += 4

        if (self._data_len - i) < self._frame_payload_len:
            raise _NotEnoughFrame()

        self._frame_header_len = i

    def _extractMessageFromFrame(self, data):
        i = self._frame_header_len

        # when payload is masked, extract frame mask
        frame_mask = None
        frame_mask_array = []
        if self._frame_mask:
            frame_mask = data[i - 4:i]
            for j in range(0, 4):
                frame_mask_array.append(ord(frame_mask[j]))
            payload = bytearray(data[i:i + self._frame_payload_len])
            for k in range(0, self._frame_payload_len):
                payload[k] ^= frame_mask_array[k % 4]

            return str(payload)
        else:
            return data[i:i+self._frame_payload_len]

    def sendMessage(self, message, code=0x81):
        if isinstance(message, str):
            message = message.encode('utf8')
        length = len(message)
        newFrame = []
        newFrame.append(code)
        newFrame = bytearray(newFrame)
        if length <= 125:
            newFrame.append(length)
        elif length > 125 and length < 65536:
            newFrame.append(126)
            newFrame += struct.pack('!H', length)
        elif length >= 65536:
            newFrame.append(127)
            newFrame += struct.pack('!Q', length)

        newFrame += message
        self.transport.write(str(newFrame))


class WebSocketProtocol76(WebSocketProtocol):
    def __init__(self, handler):
        WebSocketProtocol.__init__(self, handler)

        self._k1 = None
        self._k2 = None
        self._nonce = None

        self._postheader = False
        self._protocol = None

        self._frame_decoder = Hixie76FrameDecoder()

    def acceptConnection(self):
        if "Sec-Websocket-Key1" not in self.request.headers or \
            "Sec-Websocket-Key2" not in self.request.headers:
            log.msg('Using old ws spec (draft 75)')
            ws_origin_header = "WebSocket-Origin"
            ws_location_header = "WebSocket-Location"
            self._protocol = 75
        else:
            log.msg('Using ws draft 76 header exchange')
            self._k1 = self.request.headers["Sec-WebSocket-Key1"]
            self._k2 = self.request.headers["Sec-WebSocket-Key2"]
            ws_origin_header = "Sec-WebSocket-Origin"
            ws_location_header = "Sec-WebSocket-Location"
            self._protocol = 76

        self.transport.write(
            "HTTP/1.1 101 Web Socket Protocol Handshake\r\n"
            "Upgrade: WebSocket\r\n"
            "Connection: Upgrade\r\n"
            "Server: cyclone/%s\r\n"
            "%s: %s\r\n"
            "%s: ws://%s%s\r\n\r\n" %
            (cyclone.version, ws_origin_header, self.request.headers["Origin"],
             ws_location_header, self.request.host, self.request.path))
        self._postheader = True

    def _handleClientChallenge(self, data):
        # accumulate data until the challenge token from client is complete
        # return None if not enough data to form the challenge has been passed,
        # a string (eventually empty) of the rest of the bytes not used for the
        # challenge
        if self._nonce is None:
            self._nonce = data[:8]
            rest = data[8:]
        else:
            bytes_remaining = 8 - len(self._nonce)
            self._nonce += data[:bytes_remaining]
            rest = data[bytes_remaining:]

        # if self._nonce is complete, return the remaining data (eventually '')
        # else, return None to signal that nonce has not yet been completely
        # received
        return rest if len(self._nonce) == 8 else None

    def rawDataReceived(self, data):
        if self._postheader is True and self._protocol >= 76:
            rest = self._handleClientChallenge(data)
            if rest is None:
                # not enough bytes for the challenge data, process later
                return
            else:
                # process challenge and (eventually) process remaining data by
                # calling rawDataReceived with the rest of data
                token = self._calculate_token(self._k1, self._k2,
                                              self._nonce)
                self.transport.write(token)
                self._postheader = False
                self.handler._connectionMade()
                self.rawDataReceived(rest)
                return

        # process websocket frames
        try:
            frames = self._frame_decoder.feed(data)
            for message in frames:
                if message is None:
                    # incomplete frame, wait for more data
                    return
                elif message is self._frame_decoder.CLOSING_FRAME:
                    self.close()
                else:
                    self.handler.messageReceived(message)
        except Exception as e:
            log.msg("Invalid WebSocket data: %r" % e)
            self.handler._handle_request_exception(e)
            self.transport.loseConnection()

    def close(self):
        self.transport.write('\xff\x00')
        self.transport.loseConnection()

    def sendMessage(self, message):
        self.transport.write("\x00%s\xff" % message)

    def _calculate_token(self, k1, k2, k3):
        token = struct.pack('>II8s', self._filterella(k1),
                            self._filterella(k2), k3)
        return hashlib.md5(token).digest()

    def _filterella(self, w):
        nums = []
        spaces = 0
        for l in w:
            if l.isdigit():
                nums.append(l)
            if l.isspace():
                spaces = spaces + 1
        x = int(''.join(nums)) / spaces
        return x


class FrameDecodeError(Exception):
    """ Frame Decode Error """


class Hixie76FrameDecoder(object):
    """
    Hixie76 Frame Decoder
    """

    # represents a closing frame
    CLOSING_FRAME = object()

    # possible states for the frame decoder
    WAIT_FOR_FRAME_TYPE = 0   # waiting for the frame type byte
    INSIDE_FRAME = 1          # inside a frame and accumulating bytes until the
                              # end of it
    WAIT_FOR_CLOSE = 2        # frame type was \xff, waiting for \x00 to form a
                              # closing frame

    def __init__(self):
        self._state = self.WAIT_FOR_FRAME_TYPE  # current state
        self._frame = []  # accumulates frame message

    def feed(self, data):
        """
        Feed the frame decode with new data. Returns a list of the resulting
        frames or [] if the input data is insufficient to form a valid frame.
        """
        res = []
        for b in data:
            frame = self._feed_byte(b)
            if frame is not None:
                res.append(frame)
                if frame is self.CLOSING_FRAME:
                    break  # no need to process data which will be discarded
        return res

    def _feed_byte(self, b):
        if self._state == self.WAIT_FOR_FRAME_TYPE:
            if b == '\x00':
                # start of a new frame
                self._state = self.INSIDE_FRAME
                self._frame = []
                return None
            elif b == '\xff':
                # start of a closing frame
                self._state = self.WAIT_FOR_CLOSE
                self._frame = []
                return None
            else:
                raise FrameDecodeError("Invalid byte '%r' while waiting for "
                                       "a new frame" % b)
        elif self._state == self.INSIDE_FRAME:
            if b == '\xff':
                # end of frame: reset state, form the new frame and return it
                self._state = self.WAIT_FOR_FRAME_TYPE
                frame = ''.join(self._frame)
                self._frame = []
                return frame
            else:
                # accumulate frame data
                self._frame.append(b)
        elif self._state == self.WAIT_FOR_CLOSE:
            if b == '\x00':
                # closing frame received
                self._state = self.WAIT_FOR_FRAME_TYPE
                self._frame = []
                return self.CLOSING_FRAME
            else:
                raise FrameDecodeError("Invalid byte '%r' while waiting for "
                                       "close message" % b)
        else:
            raise FrameDecodeError("Invalid decoder state. "
                                   "This shouldn't happen")
