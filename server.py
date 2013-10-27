import errno
import functools
import socket
import time
from images2gif import GifWriter
# import gifwriter as gw
# import gifWriter2 as gw2
from io import BytesIO
from tornado import ioloop, iostream
from PIL import Image, ImageFont, ImageFile, ImageDraw, ImagePalette
import gifplugin as GifImagePlugin
# from gifplugin import i8,o8,i16,o16
# import gifmaker as gm

MARGIN = 2
FONT = ImageFont.truetype("anony.ttf",12)

def connection_ready(sock, fd, events):
    print "CONN READY"
    gif = ""
    with open('/Users/njohnson/Downloads/earf.gif') as fp:
        gif = fp.read()
    # print gif

    while True:
        try:
            connection, address = sock.accept()
        except socket.error, e:
            if e[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            return
        connection.setblocking(0)
        stream = iostream.IOStream(connection)
        stream.write("HTTP/1.0 200 OK\r\n")
        stream.write("Content-Type: image/gif\r\n")
        stream.write("\r\n")
        # stream.write(gif, stream.close)

        images = []
        palettes = []
        for i in range(7):
            img = Image.new("RGB", (600,100))
            draw = ImageDraw.Draw(img)
            for j in range(i):
                draw.text((MARGIN,MARGIN+(j*16)), "".join(chr(x) for x in range(33,200)), (0,255,0), font=FONT)
            img = img.convert("P")
            img.encoderinfo = {}
            palette = img.im.getpalette("RGB")[:768]
            img.putpalette(palette)
            palettes.append(palette)
            images.append(img)

        # rio = BytesIO()
        rio = stream
        gifWriter = GifWriter()
        gifWriter.transparency = False
        loops = 1
        xy = [(0,0) for im in images]
        dispose = [2 for im in images]
        duration = [3.0 for im in images]
        globalPalette = palettes[0]

        # Init
        frames = 0
        firstFrame = True


        
        for im, palette in zip(images, palettes):
        
            if firstFrame:
                # Write header
        
                # Gather info
                header = gifWriter.getheaderAnim(im)
                appext = gifWriter.getAppExt(loops)
                print "WRITING GIF HEADER"
                # Write
                rio.write(header)
                rio.write(globalPalette)
                rio.write(appext)
        
                # Next frame is not the first
                firstFrame = False
        
            if True:
                # Write palette and image data
        
                # Gather info
                data = GifImagePlugin.getdata(im)
                imdes, data = data[0], data[1:]

                transparent_flag = 0
                
                graphext = gifWriter.getGraphicsControlExt(duration[frames],
                    dispose[frames],transparent_flag=transparent_flag,transparency_index=255)

                # Make image descriptor suitable for using 256 local color palette
                lid = gifWriter.getImageDescriptor(im, xy[frames])
        
                # Write local header
                # Use global color palette
                print "WRITING GIF FRAME"
                rio.write(graphext)
                rio.write(imdes) # write suitable image descriptor
        
                # Write image data
                for d in data:
                    rio.write(d)

                # print len(rio.getvalue())
                import time;time.sleep(3)
        
            # Prepare for next round
            frames = frames + 1
        
        stream.write(";")  # end gif

        stream.close()
 
if __name__ == '__main__':
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0)
    sock.bind(("", 8010))
    sock.listen(5000)
 
    io_loop = ioloop.IOLoop.instance()
    callback = functools.partial(connection_ready, sock)
    io_loop.add_handler(sock.fileno(), callback, io_loop.READ)
    try:
        io_loop.start()
    except KeyboardInterrupt:
        io_loop.stop()
        print "exited cleanly"
