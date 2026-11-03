import json
import os
import socket
import tempfile
import threading
import unittest

from playerpicker.protocol import (
    MAX_MESSAGE_BYTES,
    ProtocolError,
    decode_message,
    encode_message,
    error_response,
    send_request,
    validate_request,
)


class MessageTests(unittest.TestCase):
    def test_round_trip(self):
        payload = {"action": "set_slot", "path": "/dev/input/event1", "slot": 2}
        self.assertEqual(decode_message(encode_message(payload)), payload)

    def test_encode_appends_newline(self):
        self.assertTrue(encode_message({"action": "get_state"}).endswith(b"\n"))

    def test_reject_non_objects(self):
        with self.assertRaises(ProtocolError):
            decode_message(b"[1, 2, 3]")
        with self.assertRaises(ProtocolError):
            decode_message(b"not json")
        with self.assertRaises(ProtocolError):
            decode_message(b"")

    def test_reject_oversized_messages(self):
        raw = b'{"action":"' + b"x" * MAX_MESSAGE_BYTES + b'"}'
        with self.assertRaises(ProtocolError):
            decode_message(raw)
        with self.assertRaises(ProtocolError):
            encode_message({"action": "x" * MAX_MESSAGE_BYTES})

    def test_validate_request(self):
        self.assertEqual(validate_request({"action": "get_state"}), "get_state")
        for payload in ({}, {"action": ""}, {"action": 1}):
            with self.assertRaises(ProtocolError):
                validate_request(payload)

    def test_error_response_shape(self):
        self.assertEqual(error_response("boom"), {"status": "error", "error": "boom"})


class SendRequestTests(unittest.TestCase):
    def test_reads_fragmented_response(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "test.sock")
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(path)
            server.listen(1)

            def serve():
                connection, _ = server.accept()
                with connection:
                    connection.recv(4096)
                    payload = json.dumps({"status": "ok", "slots": 4}).encode()
                    connection.sendall(payload[:5])
                    connection.sendall(payload[5:])
                server.close()

            thread = threading.Thread(target=serve)
            thread.start()
            try:
                response = send_request(path, {"action": "get_state"})
            finally:
                thread.join(timeout=2)
            self.assertEqual(response, {"status": "ok", "slots": 4})


if __name__ == "__main__":
    unittest.main()
