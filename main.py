import mimetypes
import socket
import logging

from urllib.parse import urlparse, unquote_plus
from http.server import HTTPServer, BaseHTTPRequestHandler
from pymongo.mongo_client import MongoClient
from datetime import datetime

# from pymongo.server_api import ServerApi
from threading import Thread
from pathlib import Path

URI = "mongodb://mongoserver:27017/"
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR.joinpath("src")
BUFFER_SIZE = 1024
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 3000
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 5000


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path

        match route:
            case "/":
                self.send_html_file("src/index.html")
            case "/message":
                self.send_html_file("src/message.html")
            case _:
                file = STATIC_DIR.joinpath(route[1:])
                print("File", file)
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html_file("src/error.html", status=404)

    def do_POST(self):
        size = self.headers.get("Content-length")
        data = self.rfile.read(int(size)).decode()

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.sendto(data.encode(), (SOCKET_HOST, SOCKET_PORT))
        client_socket.close()

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header("content-type", "text/html")
        self.end_headers()
        try:
            with open(filename, "rb") as fd:
                self.wfile.write(fd.read())
        except FileNotFoundError:
            print(f"Oooops, file {filename} not found")
        except Exception as e:
            print(f"Unexpected error: {e}")

    def send_static(self, filename):
        self.send_response(200)
        mime_type = mimetypes.guess_type(self.path)
        mime_type = mime_type[0] if mime_type else "text/plain"
        self.send_header("Content-type", mime_type)
        self.end_headers()
        try:
            with open(filename, "rb") as fd:
                self.wfile.write(fd.read())
        except FileNotFoundError:
            logging.error(f"Oooops, file {filename} not found")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")


def save_data(data):
    client = MongoClient(URI)
    db = client.homework6
    data = unquote_plus(data.decode())

    try:
        parsed_data = {
            key: value for key, value in [el.split("=") for el in data.split("&")]
        }
        parsed_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.messages.insert_one(parsed_data)
    except ValueError as e:
        logging.error(f"Parsing error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while data saving: {e}")
    finally:
        logging.info(f"Database connection closed")
        client.close()


def run_http_server(server_class=HTTPServer, handler_class=RequestHandler):
    server_address = (HTTP_HOST, HTTP_PORT)
    httpd = server_class(server_address, handler_class)
    logging.info(f"Http server started at port {HTTP_PORT}")
    try:
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        logging.info("Http server stopped")
        httpd.server_close()


def run_socket_server():
    soc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    soc.bind((SOCKET_HOST, SOCKET_PORT))
    logging.info(f"Socket server started on port: {SOCKET_PORT}")
    try:
        while True:
            data, addr = soc.recvfrom(BUFFER_SIZE)
            logging.info(f"Received message from {addr}: {data.decode()}")
            save_data(data)
            logging.info("Message saved to database")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        logging.info("Socket server stopped")
        soc.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(threadName)s - %(message)s"
    )

    http_thread = Thread(target=run_http_server, name="HTTP")
    http_thread.start()

    socket_thread = Thread(target=run_socket_server, name="SOCKET")
    socket_thread.start()
