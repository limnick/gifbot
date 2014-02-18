import errno
import functools
import socket
import datetime
import os
import gifplugin as GifImagePlugin
from collections import deque
from images2gif import GifWriter
from io import BytesIO
from tornado import ioloop, iostream
from PIL import Image, ImageFont, ImageDraw
from irctest import IRCConn
from .local import IRC_PASS, SECRET_NICKS

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

LAST_FRAME,HEADER_DATA = None,None

CLOSE_ON_TIMEOUT = True

BOT_NAME = "gifbot"
IRC_NETWORK = "irc.synirc.net"

BIND_ADDR = "0.0.0.0"
BIND_PORT = 80

TIME_STEP = 4
MAX_TIME = 60

LINE_SPACING = 14
MARGIN = 2
FONT = ImageFont.truetype(os.path.join(BASE_PATH, "anony.ttf"), 12)

streams = set()
output_buffer = deque(["" for _ in range(6)])

gifWriter = GifWriter()
gifWriter.transparency = False

def get_header_data():
    rio = BytesIO()
    img,palette = gen_img()

    header = gifWriter.getheaderAnim(img)
    appext = gifWriter.getAppExt(1) #num loops

    rio.write(header)
    rio.write(palette)
    rio.write(appext)
    return rio.getvalue()

def new_msg(msg):
    output_buffer.append(msg.decode("utf-8", 'ignore'))
    if len(output_buffer) > 6:
        output_buffer.popleft()

def connection_ready(sock, fd, events):
    while True:
        try:
            connection, address = sock.accept()
        except socket.error, e:
            if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            return

        connection.setblocking(0)
        handle_connection(connection, address)

def _handle_headers(stream, data):
    lines = data.split("\r\n")
    request,headers = lines[0],lines[1:-2]
    for header in headers:
        try:
            param,val = map(str.strip, header.split(":"))
        except ValueError:
            continue

        if param == "User-Agent":
            ua = val.lower()
            is_mobile = bool(sum([x in ua for x in ['android', 'webos', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']]))
            if is_mobile:
                stream.close()

def closestream(stream):
    if not stream.closed():
        stream.write(";")
        stream.close()

def handle_connection(connection, address):
    stream = iostream.IOStream(connection)
    callback = functools.partial(_handle_headers, stream)
    stream.read_until("\r\n\r\n", callback)
    stream.write("HTTP/1.0 200 OK\r\n")
    stream.write("Content-Type: image/gif\r\n")
    stream.write("\r\n")
    
    stream.write(HEADER_DATA)
    stream.write(LAST_FRAME)
    if CLOSE_ON_TIMEOUT:
        callback = functools.partial(closestream, stream)
        ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=MAX_TIME), callback)
    streams.add(stream)

def send_latest():
    global streams, LAST_FRAME
    latest_gif = get_img_frame()
    
    del LAST_FRAME
    LAST_FRAME = latest_gif

    new_streams = set()
    for stream in streams:
        if not stream.closed():
            stream.write(latest_gif)
            new_streams.add(stream)

    del streams
    streams = new_streams

def gen_img():
    img = Image.new("RGB", (600,100))
    draw = ImageDraw.Draw(img)

    draw.text((MARGIN,MARGIN+(LINE_SPACING*6)), "----------- [{: ^18s}] ------ #yospos ------ synirc ------------".format(str(len(streams))+" viewers"), (0,255,0), font=FONT)
    for i,line in enumerate(output_buffer):
        draw.text((MARGIN,MARGIN+(i*LINE_SPACING)), line, (0,255,0), font=FONT)
    img = img.convert("P")
    palette = img.im.getpalette("RGB")[:768]
    return img, palette

def get_img_frame():
    img, palette = gen_img()
    rio = BytesIO()
    
    data = GifImagePlugin.getdata(img)
    imdes, data = data[0], data[1:]
    graphext = gifWriter.getGraphicsControlExt(duration=TIME_STEP)

    rio.write(graphext)
    rio.write(imdes)

    for d in data:
        rio.write(d)
    
    return rio.getvalue()

def chanmsg(self, channel, username, message):
    if username in SECRET_NICKS:
        username = "YOSPOSTER"
    new_msg("{}: {}".format(username, message))
    if message.startswith("!watchers"):
        msg = "There are {} open sockets. ".format(len(streams))
        self.chanmsg("#yospos", msg)
    # print "CHANMSG ", channel, username, message, ""

if __name__ == '__main__':
    LAST_FRAME = get_img_frame()
    HEADER_DATA = get_header_data()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0)
    sock.bind((BIND_ADDR, BIND_PORT))
    sock.listen(5000)

    io_loop = ioloop.IOLoop.instance()
    callback = functools.partial(connection_ready, sock)
    io_loop.add_handler(sock.fileno(), callback, io_loop.READ)

    irc = IRCConn(BOT_NAME, BOT_NAME, io_loop)
    irc.on_chanmsg = functools.partial(chanmsg, irc)
    irc.connect(IRC_NETWORK, 6667)

    def joinirc(irc):
        irc.join("#yospos")
    cb = functools.partial(joinirc, irc)

    def register(irc):
        irc.privmsg('nickserv', "identify {}".format(IRC_PASS))
    reg = functools.partial(joinirc, irc)

    io_loop.add_timeout(datetime.timedelta(seconds=6), reg)
    io_loop.add_timeout(datetime.timedelta(seconds=8), cb)

    send_loop = ioloop.PeriodicCallback(send_latest, TIME_STEP*1000)
    send_loop.start()
    try:
        io_loop.start()
    except KeyboardInterrupt:
        send_loop.stop()
        io_loop.stop()
        print "exited cleanly"
