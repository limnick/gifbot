import errno
import functools
import socket
import time
import datetime
from collections import deque
from images2gif import GifWriter
from io import BytesIO
from tornado import ioloop, iostream
from PIL import Image, ImageFont, ImageFile, ImageDraw, ImagePalette
import gifplugin as GifImagePlugin
from irctest import IRCConn
import os

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

TIME_STEP = 5
MAX_TIME = 60

MARGIN = 2
FONT = ImageFont.truetype(os.path.join(BASE_PATH, "anony.ttf"),12)
streams = set()

output_buffer = deque(["" for _ in range(7)])

gifWriter = GifWriter()
gifWriter.transparency = False

def get_header_data():
    rio = BytesIO()
    img = Image.new("RGB", (600,100))
    draw = ImageDraw.Draw(img)
    draw.text((MARGIN,MARGIN), "asdf", (0,255,0), font=FONT)
    img = img.convert("P")
    img.encoderinfo = {}
    palette = img.im.getpalette("RGB")[:768]
    img.putpalette(palette)

    # Write header
    # Gather info
    header = gifWriter.getheaderAnim(img)
    appext = gifWriter.getAppExt(1) #num loops
    # Write
    rio.write(header)
    rio.write(palette)
    rio.write(appext)
    return rio.getvalue()

HEADER_DATA = get_header_data()

def new_msg(msg):
    output_buffer.append(msg.decode("utf-8", 'ignore'))
    if len(output_buffer) > 7:
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
    global streams
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
    callback = functools.partial(closestream, stream)
    ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=MAX_TIME), callback)
    streams.add(stream)

def send_latest():
    global streams
    latest_gif = get_img_frame()

    new_streams = set()
    for stream in streams:
        if not stream.closed():
            stream.write(latest_gif)
            new_streams.add(stream)
    streams = new_streams

def gen_img():
    img = Image.new("RGB", (600,100))
    draw = ImageDraw.Draw(img)
    for i,line in enumerate(output_buffer):
        draw.text((MARGIN,MARGIN+(i*14)), line, (0,255,0), font=FONT)
    img = img.convert("P")
    img.encoderinfo = {}
    palette = img.im.getpalette("RGB")[:768]
    img.putpalette(palette)
    return img, palette

def get_img_frame():
    img, palette = gen_img()
    rio = BytesIO()
    
    # Write palette and image data
    # Gather info
    data = GifImagePlugin.getdata(img)
    imdes, data = data[0], data[1:]
    graphext = gifWriter.getGraphicsControlExt(duration=TIME_STEP)

    # Write local header
    # Use global color palette
    rio.write(graphext)
    rio.write(imdes) # write suitable image descriptor

    # Write image data
    for d in data:
        rio.write(d)
    
    return rio.getvalue()
 
def chanmsg(self, channel, username, message):
    new_msg("{}: {}".format(username, message))
    print repr(message)
    if message.startswith("!watchers"):
        msg = "There are {} open sockets. ".format(len(streams))
        self.chanmsg("#yospos", msg)
    print "CHANMSG ", channel, username, message, ""

if __name__ == '__main__':

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0)
    sock.bind(("0.0.0.0", 80))
    sock.listen(5000)

    io_loop = ioloop.IOLoop.instance()
    callback = functools.partial(connection_ready, sock)
    io_loop.add_handler(sock.fileno(), callback, io_loop.READ)

    irc = IRCConn("gifbot", "gifbot", io_loop)
    irc.on_chanmsg = functools.partial(chanmsg, irc)
    irc.connect('irc.synirc.net', 6667)

    def joinirc(irc):
        irc.join("#yospos")
    cb = functools.partial(joinirc, irc)

    io_loop.add_timeout(datetime.timedelta(seconds=10), cb)

    send_loop = ioloop.PeriodicCallback(send_latest, TIME_STEP*1000)
    send_loop.start()
    try:
        io_loop.start()
    except KeyboardInterrupt:
        send_loop.stop()
        io_loop.stop()
        print "exited cleanly"
