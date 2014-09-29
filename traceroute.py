import errno
import functools
import socket
import datetime
import os
import gifplugin as GifImagePlugin
from images2gif import GifWriter
from io import BytesIO
from tornado import ioloop, iostream, process
from PIL import Image, ImageFont, ImageDraw

BASE_PATH = os.path.dirname(os.path.realpath(__file__))

HEADER_DATA = None

CLOSE_ON_TIMEOUT = True

BIND_ADDR = "0.0.0.0"
BIND_PORT = 8000

TIME_STEP = 4
MAX_TIME = 60

LINE_SPACING = 14
MARGIN = 2
FONT = ImageFont.truetype(os.path.join(BASE_PATH, "anony.ttf"), 12)

streams = []

gifWriter = GifWriter()
gifWriter.transparency = False

def _get_init_img_frame():
    img = Image.new("RGB", (600,100))
    draw = ImageDraw.Draw(img)
    for i,line in enumerate(["", "", " -- LOADING -- ", "", "", ""]):
        draw.text((MARGIN,MARGIN+(i*LINE_SPACING)), line, (0,255,0), font=FONT)
    img = img.convert("P")
    palette = img.im.getpalette("RGB")[:768]
    rio = BytesIO()
    data = GifImagePlugin.getdata(img)
    imdes, data = data[0], data[1:]
    graphext = gifWriter.getGraphicsControlExt(duration=TIME_STEP)
    rio.write(graphext)
    rio.write(imdes)
    for d in data:
        rio.write(d)
    return rio.getvalue()
INITIAL_FRAME = _get_init_img_frame()

def get_header_data():
    rio = BytesIO()
    img = Image.new("RGB", (600,100))
    img = img.convert("P")
    palette = img.im.getpalette("RGB")[:768]

    header = gifWriter.getheaderAnim(img)
    appext = gifWriter.getAppExt(1) #num loops

    rio.write(header)
    rio.write(palette)
    rio.write(appext)
    return rio.getvalue()

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
    stream.write(INITIAL_FRAME)

    #exec traceroute against host ip
    remote_ip = address[0]
    remote_ip = "google.com"
    traceroute_proc = process.Subprocess(['traceroute', '-w', '5', '-q', '1', '-S', remote_ip], stdout=process.Subprocess.STREAM)
    traceroute_proc.initialize()

    output_buffer = []
    def _handleResult(result):
        output_buffer.append(result)
        print "AA", result, repr(output_buffer)
    result = traceroute_proc.stdout.read_until_close(callback=_handleResult, streaming_callback=_handleResult)

    if CLOSE_ON_TIMEOUT:
        #TODO: also kill traceroute_proc
        callback = functools.partial(closestream, stream)
        ioloop.IOLoop.instance().add_timeout(datetime.timedelta(seconds=MAX_TIME), callback)

    streams.append((stream, traceroute_proc, output_buffer, 0))

def send_latest():
    global streams
    print "SS", len(streams)

    new_streams = []
    for stream, traceroute_proc, output_buffer, buffer_index in streams:
        print "s", stream, traceroute_proc, output_buffer, buffer_index
        if not stream.closed():
            print "SEND", repr(output_buffer)
            latest_gif = get_img_frame(output_buffer, buffer_index)
            stream.write(latest_gif)
            new_streams.append((stream, traceroute_proc, output_buffer, buffer_index))

    del streams
    streams = new_streams

def gen_img(output_buffer, buffer_index):
    img = Image.new("RGB", (600,100))
    draw = ImageDraw.Draw(img)

    for i,line in enumerate(output_buffer):
        draw.text((MARGIN,MARGIN+(i*LINE_SPACING)), line, (0,255,0), font=FONT)

    img = img.convert("P")
    palette = img.im.getpalette("RGB")[:768]
    return img, palette

def get_img_frame(output_buffer, buffer_index):
    img, palette = gen_img(output_buffer, buffer_index)
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
    HEADER_DATA = get_header_data()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0)
    sock.bind((BIND_ADDR, BIND_PORT))
    sock.listen(5000)

    io_loop = ioloop.IOLoop.instance()
    callback = functools.partial(connection_ready, sock)
    io_loop.add_handler(sock.fileno(), callback, io_loop.READ)

    send_loop = ioloop.PeriodicCallback(send_latest, TIME_STEP*1000)
    send_loop.start()
    try:
        io_loop.start()
    except KeyboardInterrupt:
        send_loop.stop()
        io_loop.stop()
        print "exited cleanly"
