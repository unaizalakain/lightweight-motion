import logging
import os
import cv2
from datetime import datetime
from time import sleep
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn


class Window(object):
    def __init__(self, frames):
        self.frames = frames

    def run(self):
        logging.debug('Openning window')
        for frame in self.frames:
            cv2.imshow('camera', frame)
            if cv2.waitKey(5) == 27:
                break


class HTTPStream(object):
    class CameraHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type',
                    'multipart/x-mixed-replace; '
                    'boundary=--ipcamera')
            self.end_headers()
            for frame in self.frames:
                retval, frame = cv2.imencode('.jpeg', frame)
                frame = frame.tostring()
                self.wfile.write('--ipcamera\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                sleep(0.05)

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        pass

    def __init__(self, frames, host, port):
        self.host, self.port = host, port
        self.frames = frames
        self.handler = self.CameraHandler
        self.handler.frames = self.frames
        self.server = self.ThreadedHTTPServer((host, port), self.handler)

    def run(self):
        logging.debug('Openning HTTP stream output at {host}:{port}'.format(
            host=self.host, port=self.port))
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            self.server.socket.close()


class EventDirectory(object):
    def __init__(self, events, store_path, prefix='capture'):
        self.events = events
        self.store_path = store_path
        self.prefix = prefix
        if not os.path.isdir(self.store_path):
            logging.warning('Directory {} does not exist'.format(self.store_path))
            os.mkdir(self.store_path)
            logging.warning('Directory {} created'.format(self.store_path))

    @property
    def available_space(self):
        st = os.statvfs(self.store_path)
        return st.f_bavail * st.f_frsize

    def make_space(self, reservation):
        if self.available_space < reservation:
            logging.warning('No free space available, proceeding to making space')
            for dirname in sorted(os.listdir(self.store_path)):
                dirname = os.path.join(self.store_path, dirname)
                for filename in sorted(os.listdir(dirname)):
                    filename = os.path.join(dirname, filename)
                    os.remove(filename)
                    logging.info('Deleted {} to avoid filling disk'.format(filename))
                    if self.available_space > reservation:
                        logging.info('Free space now available')
                        return

    def capture_filename(self):
        now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S-%f')
        return '{}-{}'.format(self.prefix, now)

    def save_event(self, event):
        dirname = os.path.join(self.store_path, self.capture_filename())
        os.mkdir(dirname)
        logging.info('Saving motion event at {}'.format(dirname))
        for frame in event:
            self.make_space(40 * 1024**2)
            filename = '{}.jpg'.format(self.capture_filename())
            filename = os.path.join(dirname, filename)
            cv2.imwrite(filename, frame)
            logging.debug('Frame {} saved'.format(filename))

    def run(self):
        for event in self.events:
            logging.info('New motion event detected')
            self.save_event(event)
