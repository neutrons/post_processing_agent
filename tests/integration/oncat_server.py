from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import logging

logging.basicConfig(filename="oncat_server.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    """Fake ONCat server for testing purposes"""

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer test-token":
            self.send_response(403)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"error": "Forbidden"}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        # Handle batch cataloging endpoint
        if self.path == "/api/datafiles/batch":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                file_paths = json.loads(body.decode("utf-8"))
                if not isinstance(file_paths, list):
                    self.send_response(400)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    response = {"error": "Expected array of file paths"}
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    return

                logging.info("Received batch datafile ingest request for %d files", len(file_paths))
                for file_path in file_paths:
                    logging.info("  - %s", file_path)

                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response = {"ingested": len(file_paths)}
                self.wfile.write(json.dumps(response).encode("utf-8"))
                return
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                logging.error("Batch ingestion error: %s", str(e))
                response = {"error": str(e)}
                self.wfile.write(json.dumps(response).encode("utf-8"))
                return

        if self.path.startswith("/api/datafiles/"):
            location = self.path.replace("/api/datafiles", "").replace("/ingest", "")
            logging.info("Received datafile ingest request for %s", location)
        elif self.path.startswith("/api/reductions/"):
            location = self.path.replace("/api/reductions", "").replace("/ingest", "")
            logging.info("Received reduction ingest request for %s", location)
        else:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            logging.error("Unknown endpoint: %s", self.path)
            response = {"error": "Unknown endpoint"}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        if not os.path.isfile(location):
            self.send_response(404)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            logging.error("File not found: %s", location)
            response = {"error": "File not found"}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        try:
            # assume the format /facility/instrument/experiment/nexus/instrument_run_number.nxs.h5
            # the real server would be more complex
            _, facility, instrument, experiment, *_, filename = location.split("/")
            run_number = int(filename.split("_")[-1].split(".")[0])
        except Exception:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            logging.error("Invalid path format: %s", location)
            response = {"error": "Invalid path format"}
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        # Send response
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response = {
            "location": location,
            "facility": facility,
            "instrument": instrument,
            "experiment": experiment,
            "indexed": {"run_number": run_number},
        }

        # Add metadata for VENUS instrument to support image cataloging
        if instrument == "VENUS":
            response["metadata"] = {"entry": {"daslogs": {"bl10:exp:im:imagefilepath": {"value": "images"}}}}

        self.wfile.write(json.dumps(response).encode("utf-8"))


def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
