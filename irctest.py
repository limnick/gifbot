import logging
import re
import socket
import ssl

import tornado.ioloop
import tornado.iostream

IRC_DISCONNECTED = 0
IRC_NICK = 1
IRC_CONNECTING = 2
IRC_CONNECTED = 3

PING_RE=re.compile('PING (?P<message>.+)')
CHANMSG_RE=re.compile(':(?P<username>[^!]+)!(?P<who>[^ ]+) PRIVMSG (?P<chan>#[^ ]+) :(?P<msg>.*)')
PRIVMSG_RE=re.compile(':(?P<username>[^!]+)!(?P<who>[^ ]+) PRIVMSG (?P<user>[^#][^ ]*) :(?P<msg>.*)')
ERROR_RE=re.compile('ERROR :(?P<msg>.*)')


class IRCConn(object):
    def __init__(self, nickname, full_name="Tornado IRC", io_loop=None):
        if not io_loop:
            io_loop = tornado.ioloop.IOLoop.instance()
        self.nickname = nickname
        self.io_loop = io_loop
        self.full_name = full_name
        self.conn = None
        self._state = IRC_DISCONNECTED

    def on_connect(self):
        """Callback that is invoked after connection"""
        pass

    def on_chanmsg(self, channel, username, message):
        """Callback that is invoked on every channel message"""
        pass

    def on_privmsg(self, username, message):
        """Callback taht is invoked on every private message"""
        pass

    def connect(self, host, port, do_ssl=False, password=None):
        sock = None
        self._last_connection = (host, port, do_ssl, password)
        self._password = password
        for (family, socktype, proto, canonname, sockaddr) in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM, 0):
            try:
                fd = socket.socket(family, socktype, proto)
                fd.connect(sockaddr)
                fd.setblocking(0)
                sock = fd
                break
            except socket.error:
                pass
        if not sock:
            raise socket.error("Unable to connect to %s:%s" % (host, port))
        if do_ssl:
            sock = ssl.wrap_socket(sock, server_side=False, do_handshake_on_connect=False)
            self.conn = tornado.iostream.SSLIOStream(sock, io_loop=self.io_loop)
        else:
            self.conn = tornado.iostream.IOStream(sock, io_loop=self.io_loop)
        self.conn.read_until("\n", self._handle_data)

    def _write(self, data, *args, **kwargs):
        logging.debug('<<< %s', data)
        self.conn.write(data + '\r\n', *args, **kwargs)

    def _handle_data(self, data):
        # print ">>>", data.rstrip()
        logging.debug(">>> %s", data.rstrip())
        ping_md = PING_RE.match(data)
        if ping_md:
            self._write("PONG " + ping_md.group('message'))
        if self._state == IRC_DISCONNECTED:
            if self._password:
                self._write("PASS %s" % self._password)
            self._state = IRC_NICK
        elif self._state == IRC_NICK:
            self._write("NICK %s" % self.nickname)
            self._write("USER %s 8 *  :%s" % (self.nickname, self.full_name))
            self._state = IRC_CONNECTING
        elif self._state == IRC_CONNECTING:
            self.on_connect()
            self._state = IRC_CONNECTED
        elif self._state == IRC_CONNECTED:
            cmd = CHANMSG_RE.match(data)
            if cmd:
                self.on_chanmsg(cmd.group('chan'), cmd.group('username'), cmd.group('msg'))
            pmd = PRIVMSG_RE.match(data)
            if pmd:
                if pmd.group('user') == self.nickname:
                    self.on_privmsg(pmd.group('username'), pmd.group('msg'))
            emd = ERROR_RE.match(data)
            if emd:
                if "Closing Link" in emd.group('msg'):
                    self.conn.close()
                    self.connect(*self._last_connection)
                    return
        self.conn.read_until("\n", self._handle_data)

    def join(self, channel):
        if not channel.startswith("#"):
            channel = "#" + channel
        self._write("JOIN " + channel)

    def chanmsg(self, channel, message):
        for line in message.split("\n"):
            self._write("PRIVMSG %s :%s" % (channel, line))

    def privmsg(self, user, message):
        self.chanmsg(user, message)

    def quit(self, message, callback=None):
        def after_quit(*args, **kwargs):
            self.conn.close()
            if callback:
                callback()
        self._write("QUIT :%s" % message, callback=after_quit)
