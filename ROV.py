import io
import logging
import os
import socketserver
import time
from http import server
from threading import Condition

import cv2  # Import OpenCV library

from picamera2 import Picamera2
from picamera2.encoders import JpegEncoder
from picamera2.outputs import FileOutput


# Define global variables
recording = False
fourcc = cv2.VideoWriter_fourcc(*'XVID')

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

  #resolution-select {
    position: absolute;
    top: 50px; /* Adjust position as desired */
    right: 10px;
  }

  /* Style the record button */
  #record-button {
    position: absolute;
    top: 80px; /* Adjust position as desired */
    left: 10px; /* Adjust position as desired */
    padding: 10px 20px; /* Add padding for better appearance */
    background-color: #ccc; /* Set background color */
    border: 1px solid #bbb; /* Add a border */
    cursor: pointer; /* Indicate clickable behavior */
  }

  #save-directory {
    position: absolute;
    top: 120px; /* Adjust position as desired */
    left: 10px; /* Adjust position as desired */
    padding: 10px 20px; /* Add padding for better appearance */
    background-color: #eee; /* Set background color */
    border: 1px solid #ddd; /* Add a border */
  }
</style>
</head>
<body>
  <img id="video-stream" src="stream.mjpg" />
  <div id="overlay">ARKPAD ROV V3 (EXPERIMENTAL)</div>

  <button id="record-button" onclick="toggleRecording()">Record</button>

  <select id="resolution-select" onchange="changeResolution()">
    <option value="640x480">Low Quality</option>
    <option value="1280x720" selected>720p</option>
    <option value="1920x1080">1080p</option>
    <option value="2560x1920">2560x1920 (Fisheye HD)</option>
  </select>

  <input type="text" id="save-directory" value="""" + save_dir + """">

  <script>
    var recording = false;

    function changeResolution() {
      var selectedResolution = document.getElementById("resolution-select").value;
      fetch('/resolution/' + selectedResolution); // Send request to change resolution
    }

    function toggleRecording() {
      recording = !recording; // Toggle recording state

      // Update button text or style based on recording state (optional)
      if (recording) {
        document.getElementById("record-button").textContent = "Stop Recording";
      } else {
        document.getElementById("record-button").textContent = "Record";
      }

      // Your existing recording logic here
    }
  </script>
</body>
</html>
"""
#######################functions
def toggleRecording():
  global recording, video_writer  # Access global variables

  recording = not recording

  if recording:
    # Start recording
    global output  # Assuming output is a StreamingOutput instance
    filename = f"recording_{time.strftime('%Y-%m-%d_%H-%

#########################
class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            if recording:
                # Convert frame to BGR format for OpenCV
                frame = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
                video_writer.write(frame)  # Write frame to video
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
picam2.configure(picam2.create_video_configuration(main={"size": (1920, 1080)}))
output = StreamingOutput()
picam2.start_recording(JpegEncoder(), FileOutput(output))

try:
    address = ('', 7123)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()
