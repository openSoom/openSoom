"""Protocol-boundary failure tests; live CSE evidence comes from cse_*_smoke.py."""
import json
from pathlib import Path
import tempfile
import unittest

import httpx

from opensoom.onem2m import CSEClient, CSEError


class CSEProtocolBoundaryTests(unittest.TestCase):
    def client(self, handler, **kwargs):
        client = CSEClient(**kwargs)
        client._http.close()
        client._http = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def test_missing_or_wrong_request_id_cannot_report_success(self):
        for response_id in (None, "another-request"):
            with self.subTest(response_id=response_id):
                headers = {"X-M2M-RSC": "2000"}
                if response_id:
                    headers["X-M2M-RI"] = response_id
                client = self.client(lambda request: httpx.Response(200, headers=headers, json={"m2m:cnt": {}}))
                with self.assertRaisesRegex(CSEError, "identifier"):
                    client.retrieve("cse-in/test")

    def test_http_success_cannot_hide_onem2m_denial(self):
        def denied(request):
            return httpx.Response(200, headers={"X-M2M-RSC": "4103", "X-M2M-RI": request.headers["X-M2M-RI"]}, json={"m2m:dbg": "denied"})
        with self.assertRaises(CSEError) as error:
            self.client(denied).retrieve("cse-in/scoped")
        self.assertEqual(error.exception.rsc, 4103)

    def test_transport_error_is_serializable_and_sanitized(self):
        def disconnected(request):
            raise httpx.ConnectError("sensitive upstream diagnostics", request=request)
        with self.assertRaises(CSEError) as error:
            self.client(disconnected).retrieve("cse-in")
        self.assertEqual(error.exception.result["rsc"], 0)
        self.assertNotIn("sensitive", str(error.exception))
        self.assertNotIn("sensitive", json.dumps(error.exception.result))

    def test_credentials_are_not_recorded_in_trace_or_returned_body(self):
        def reply(request):
            self.assertEqual(request.headers["Authorization"], "Bearer test-bearer-value")
            return httpx.Response(201, headers={"X-M2M-RSC": "2001", "X-M2M-RI": request.headers["X-M2M-RI"]}, json={"m2m:cin": {"con": {"api_key": "response-secret", "sequence": 1}}})
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "trace.jsonl"
            result = self.client(reply, bearer_token="test-bearer-value", trace_path=trace).create("cse-in/example", 4, {"m2m:cin": {"con": {"password": "request-secret"}}})
            captured = trace.read_text()
            for secret in ("test-bearer-value", "response-secret", "request-secret"):
                self.assertNotIn(secret, captured)
                self.assertNotIn(secret, json.dumps(result))
            self.assertEqual(result["body"]["m2m:cin"]["con"]["sequence"], 1)

    def test_untrusted_resource_path_cannot_change_host_or_add_query(self):
        def unexpected(request):
            self.fail("Rejected resource path reached the transport")
        client = self.client(unexpected)
        for path in ("https://elsewhere.example/private", "cse-in?token=x", "cse-in/../private"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                client.retrieve(path)


if __name__ == "__main__":
    unittest.main()
