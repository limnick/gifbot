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
from local import IRC_PASS, SECRET_NICKS, IRC_NETWORK

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

CLOSE_ON_TIMEOUT = True

BOT_NAME = "freenode_bot"
PUB_IRC_NETWORK = "irc.freenode.org"
IRC_PORT = 7000
IRC_CHAN = "#sharktopus"
DO_SSL = True

FRAME_SPINNER = "------"
SPINNER_LEN = len(FRAME_SPINNER)

IMG_WIDTH = 600
IMG_HEIGHT = 120

BIND_ADDR = "0.0.0.0"
BIND_PORT = 9000

TIME_STEP = 4
MAX_TIME = 60

FRAMECOUNT = 0

LINE_SPACING = 14
MARGIN = 2
FONT = ImageFont.truetype(os.path.join(BASE_PATH, "anony.ttf"), 12)

TOTAL_NUM_LINES = (IMG_HEIGHT / LINE_SPACING) - 1
print "tot", TOTAL_NUM_LINES

streams = set()
LAST_FRAME,HEADER_DATA = None,None
output_buffer = deque(["" for _ in range(TOTAL_NUM_LINES)])

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
    raw_msg = msg.decode("utf-8", 'ignore')
    if raw_msg.startswith("***"):
        return

    output_buffer.append(raw_msg)
    if len(output_buffer) > TOTAL_NUM_LINES:
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
    request, headers = lines[0], lines[1:-2]
    print request
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
    global streams, LAST_FRAME, FRAMECOUNT
    latest_gif = get_img_frame()

    FRAMECOUNT += 1
    if FRAMECOUNT >= SPINNER_LEN:
        FRAMECOUNT = 0

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
    img = Image.new("RGB", (IMG_WIDTH,IMG_HEIGHT))
    draw = ImageDraw.Draw(img)

    spinner_pos = FRAMECOUNT % SPINNER_LEN
    frame_spinner = FRAME_SPINNER[:spinner_pos] + '*' + FRAME_SPINNER[spinner_pos+1:]

    draw.text(
        (MARGIN,MARGIN+(LINE_SPACING*TOTAL_NUM_LINES)),
        "---- [{viewerstr: ^18s}] {frame_spinner:s} {chan: ^14s} -- {server: ^18s} ----".format(**{
            'viewerstr': str(len(streams))+" viewers",
            'frame_spinner': frame_spinner,
            'chan': IRC_CHAN,
            'server': PUB_IRC_NETWORK,
        }),
        (0,255,0),
        font=FONT)
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
        self.chanmsg(IRC_CHAN, msg)
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
    # irc.connect(IRC_NETWORK, IRC_PORT, do_ssl=True)
    irc.connect(IRC_NETWORK, IRC_PORT, do_ssl=DO_SSL, password=IRC_PASS)

    def joinirc(irc):
        irc.join(IRC_CHAN)
    cb = functools.partial(joinirc, irc)

    # def register(irc):
    #     irc.privmsg('nickserv', "identify {}".format(IRC_PASS))
    # reg = functools.partial(register, irc)

    # io_loop.add_timeout(datetime.timedelta(seconds=12), reg)
    io_loop.add_timeout(datetime.timedelta(seconds=15), cb)

    send_loop = ioloop.PeriodicCallback(send_latest, TIME_STEP*1000)
    send_loop.start()
    try:
        io_loop.start()
    except KeyboardInterrupt:
        send_loop.stop()
        io_loop.stop()
        print "exited cleanly"
