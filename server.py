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

BIND_ADDR = "0.0.0.0"
BIND_PORT = 9000

TIME_STEP = 4
MAX_TIME = 60

FRAMECOUNT = 0

LINE_SPACING = 14
MARGIN = 2
FONT = ImageFont.truetype(os.path.join(BASE_PATH, "anony.ttf"), 12)

IMAGE_DEFS = {
    'sig.gif': (600,120),
    'site.gif': (600,400),
}
DEFAULT_IMG_NAME = 'sig.gif'

BUFFER_MAX = 50
output_buffer = ["" for _ in range(BUFFER_MAX)]

gifWriter = GifWriter()
gifWriter.transparency = False

streams = {}
LAST_FRAME = {}
HEADER_DATA = {}
for img_name in IMAGE_DEFS.keys():
    streams[img_name] = set()
    LAST_FRAME[img_name] = None
    HEADER_DATA[img_name] = None


def get_header_data(width,height):
    rio = BytesIO()
    img,palette = gen_img(width,height)

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

    output_buffer.insert(0, raw_msg)
    if len(output_buffer) > BUFFER_MAX:
        output_buffer.pop()


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
    cur_img_name = DEFAULT_IMG_NAME
    for img_name in IMAGE_DEFS.keys():
        if request.startswith("GET /{}".format(img_name)):
            cur_img_name = img_name

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

    stream.write("HTTP/1.0 200 OK\r\n")
    stream.write("Content-Type: image/gif\r\n")
    stream.write("\r\n")

    stream.write(HEADER_DATA[cur_img_name])
    stream.write(LAST_FRAME[cur_img_name])
    if CLOSE_ON_TIMEOUT:
        callback = functools.partial(closestream, stream)
        ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=MAX_TIME), callback)
    streams[cur_img_name].add(stream)


def closestream(stream):
    if not stream.closed():
        stream.write(";")
        stream.close()


def handle_connection(connection, address):
    stream = iostream.IOStream(connection)
    callback = functools.partial(_handle_headers, stream)
    stream.read_until("\r\n\r\n", callback)


def send_latest():
    global streams, LAST_FRAME, FRAMECOUNT
    FRAMECOUNT += 1
    if FRAMECOUNT >= SPINNER_LEN:
        FRAMECOUNT = 0

    for img_name,img_size in IMAGE_DEFS.items():
        latest_gif = get_img_frame(*img_size)

        del LAST_FRAME[img_name]
        LAST_FRAME[img_name] = latest_gif

        new_streams = set()
        for stream in streams[img_name]:
            if not stream.closed():
                stream.write(latest_gif)
                new_streams.add(stream)

        del streams[img_name]
        streams[img_name] = new_streams


def gen_img(width,height):
    img = Image.new("RGB", (width,height))
    draw = ImageDraw.Draw(img)

    TOTAL_NUM_LINES = (height / LINE_SPACING) - 1

    num_viewers = sum(len(x) for x in streams.values())

    spinner_pos = FRAMECOUNT % SPINNER_LEN
    frame_spinner = FRAME_SPINNER[:spinner_pos] + '*' + FRAME_SPINNER[spinner_pos+1:]

    draw.text(
        (MARGIN,MARGIN+(LINE_SPACING*TOTAL_NUM_LINES)),
        "---- [{viewerstr: ^18s}] {frame_spinner:s} {chan: ^14s} -- {server: ^18s} ----".format(**{
            'viewerstr': "{} viewers".format(num_viewers),
            'frame_spinner': frame_spinner,
            'chan': IRC_CHAN,
            'server': PUB_IRC_NETWORK,
        }),
        (0,255,0),
        font=FONT)
    for i,line in enumerate(reversed(output_buffer[:TOTAL_NUM_LINES])):
        draw.text((MARGIN,MARGIN+(i*LINE_SPACING)), line, (0,255,0), font=FONT)
    img = img.convert("P")
    palette = img.im.getpalette("RGB")[:768]
    return img, palette


def get_img_frame(width,height):
    img, palette = gen_img(width,height)
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
    for img_name,img_size in IMAGE_DEFS.items():
        LAST_FRAME[img_name] = get_img_frame(*img_size)
        HEADER_DATA[img_name] = get_header_data(*img_size)

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
