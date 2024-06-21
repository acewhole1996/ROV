import io
import logging
import socketserver
from http import server
from threading import Condition

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput

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
    overflow: hidden; /* Hide any scrollbarsz */
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
  #resolution-select {
    position: absolute;
    top: 50px; /* Adjust position as desired */
    right: 10px;
  }
</style>
</head>
<body>
  <img id="video-stream" src="stream.mjpg" />
  <div id="overlay">ARKPAD ROV V3 (EXPERIMENTALx)</div>
  <button id="record-button" onclick="toggleRecording()">Record</button>
  <select id="resolution-select" onchange="changeResolution()">
    <option value="320x240">320x240</option>
    <option value="640x480" selected>640x480 (Default)</option>
    <option value="1280x720">1280x720 (HD)</option>
    <option value="1920x1080">1920x1080 (Full HD)</option>
  </select>
  <script>
    var recording = false;

    function changeResolution() {
      var selectedResolution = document.getElementById("resolution-select").value;
      fetch('/resolution/' + selectedResolution); // Send request to change resolution
    }
    function toggleRecording() {
      // ... existing recording logic ...
    }
  </script>
</body>
</html>
"""
#######################functions
def changeResolution(self):
  """
  This function updates the camera resolution and restarts recording.

  Args:
      output (StreamingOutput): The output instance used for video streaming.
  """
  try:
    # Extract resolution from path
    global picam2, output
    resolution_str = self.path.split('/')[2]
    width, height = map(int, resolution_str.split('x'))
    picam2.stop_recording()
    picam2.configure(picam2.create_video_configuration(main={"size": (width, height)}))
    picam2.start_recording(JpegEncoder(), FileOutput(output))

    self.send_response(200)
    self.send_header('Content-Type', 'text/plain')
    self.end_headers()
    self.wfile.write(b'Resolution changed to: ' + resolution_str.encode())
  except Exception as e:
    logging.warning("Error changing resolution: %s", str(e))
    self.send_error(500)
#########################
class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()

class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global picam2  # Assuming picam2 is defined globally
        #output = StreamingOutput()
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
########
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
########
        elif self.path.startswith('/resolution/'):  # Corrected indentation
            try:
                # Extract resolution from path

                resolution_str = self.path.split('/')[2]
                width, height = map(int, resolution_str.split('x'))
                picam2.stop_recording()
                picam2.configure(picam2.create_video_configuration(main={"size": (width, height)}))
                picam2.start_recording(JpegEncoder(), FileOutput(output))

                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Resolution changed to: ' + resolution_str.encode())
            except Exception as e:
                logging.warning("Error changing resolution: %s", str(e))
                self.send_error(500)

        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (320, 240)}))
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

try:
    address = ('', 7123)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()
