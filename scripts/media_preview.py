#!/usr/bin/env python3
"""Loopback-only review server with byte ranges for native MP4 seeking."""
import argparse
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class MediaHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_head(self):
        self.byte_range = None
        path = Path(self.translate_path(self.path))
        header = self.headers.get("Range")
        if not header or not path.is_file():
            return super().send_head()
        match = re.fullmatch(r"bytes=(\d+)-(\d*)", header)
        size = path.stat().st_size
        if not match:
            self.send_error(416, "Unsupported byte range")
            return None
        start = int(match[1]); end = min(int(match[2]) if match[2] else size-1, size-1)
        if start > end or start >= size:
            self.send_error(416, "Range outside media")
            return None
        stream = path.open("rb"); stream.seek(start)
        self.byte_range = (start, end)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end-start+1))
        self.end_headers()
        return stream

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def copyfile(self, source, outputfile):
        try:
            if self.byte_range is None:
                return super().copyfile(source, outputfile)
            remaining = self.byte_range[1]-self.byte_range[0]+1
            while remaining:
                chunk = source.read(min(65536, remaining))
                if not chunk:break
                outputfile.write(chunk);remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # Native players cancel earlier byte requests when a viewer seeks.
            return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]/"deliverables/video"
    def handler(*a, **kw):return MediaHandler(*a, directory=str(root), **kw)
    print(f"Local media review: http://127.0.0.1:{args.port}/preview.html", flush=True)
    try:
        ThreadingHTTPServer(("127.0.0.1",args.port),handler).serve_forever()
    except KeyboardInterrupt:
        print("Local media review stopped.")
