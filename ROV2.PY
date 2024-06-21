import io
import logging
import socketserver
from http import server
from threading import Condition
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder

# HTML page served to clients
PAGE = """\
<!DOCTYPE html>
<html>
<head>
<title>Camera Stream</title>
<style>
  body {
    margin: 0;
    padding: 0;
    height: 100vh;
    overflow: hidden; /* Hide any scrollbars */
  }

  #video-stream {
    width: 100vw;
    height: 100vh;
  }

  #overlay {
    position: absolute;
    top: 10px; /* Adjust top position for desired margin */
    left: 50%; /* Center horizontally */
    transform: translateX(-50%); /* Center horizontally with transform */
    color: white; /* Set overlay text color */
    font-size: 2em; /* Adjust font size as needed */
  }

</style>
</head>
<body>
  <img id="video-stream" src="stream.h264" />
  <div id="overlay">ARKPAD ROV V3 (EXPERIMENTAL)</div>
</body>
</html>
"""

# Streaming output class to capture frames
class StreamingOutput:
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

# Handler for serving HTTP requests
class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global picam2, output  # Assuming picam2 and output are defined globally
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.h264':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'video/h264')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(frame)
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

# Streaming server configuration
class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

# Initialize the camera and streaming output
picam2 = Picamera2()

# Function to start streaming
def start_streaming():
    global picam2, output

    try:
        picam2.start_recording(H264Encoder(), output)
        logging.info("Started streaming")
    except Exception as e:
        logging.error("Error starting streaming: %s", str(e))

# Function to stop streaming
def stop_streaming():
    global picam2

    try:
        picam2.stop_recording()
        logging.info("Stopped streaming")
    except Exception as e:
        logging.error("Error stopping streaming: %s", str(e))

# Start the HTTP server to listen for incoming connections
try:
    address = ('', 8000)  # Choose your desired port number
    server = StreamingServer(address, StreamingHandler)
    logging.info("Server started on port %s", address[1])

    # Start streaming
    start_streaming()

    # Serve indefinitely
    server.serve_forever()
except KeyboardInterrupt:
    logging.info("Keyboard interrupt received, stopping...")
finally:
    # Stop streaming and clean up
    stop_streaming()
    server.shutdown()