"""Offline tests for PyTeaser's text summarization API."""

import socket
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from types import SimpleNamespace
from unittest import TestCase, main as unittest_main
from unittest.mock import MagicMock, patch
from urllib.request import Request

from goose import Goose
from goose.network import HtmlFetcher
from goose.network import (
    SafeRedirectHandler,
    _SafeHTTPConnection,
    _read_limited,
    fetch_bytes,
    validate_url,
)
from pyteaser import Summarize, SummarizeUrl


class TestSummarize(TestCase):
    def test_text(self):
        article_title = u'Framework for Partitioning and Execution of Data Stream Applications in Mobile Cloud Computing'
        article_text = u'The contribution of cloud computing and mobile computing technologies lead to the newly emerging mobile cloud com- puting paradigm. Three major approaches have been pro- posed for mobile cloud applications: 1) extending the access to cloud services to mobile devices; 2) enabling mobile de- vices to work collaboratively as cloud resource providers; 3) augmenting the execution of mobile applications on portable devices using cloud resources. In this paper, we focus on the third approach in supporting mobile data stream applica- tions. More specifically, we study how to optimize the com- putation partitioning of a data stream application between mobile and cloud to achieve maximum speed/throughput in processing the streaming data. To the best of our knowledge, it is the first work to study the partitioning problem for mobile data stream applica- tions, where the optimization is placed on achieving high throughput of processing the streaming data rather than minimizing the makespan of executions as in other appli- cations. We first propose a framework to provide runtime support for the dynamic computation partitioning and exe- cution of the application. Different from existing works, the framework not only allows the dynamic partitioning for a single user but also supports the sharing of computation in- stances among multiple users in the cloud to achieve efficient utilization of the underlying cloud resources. Meanwhile, the framework has better scalability because it is designed on the elastic cloud fabrics. Based on the framework, we design a genetic algorithm for optimal computation parti- tion. Both numerical evaluation and real world experiment have been performed, and the results show that the par- titioned application can achieve at least two times better performance in terms of throughput than the application without partitioning.'

        summarised_article_text = [u'The contribution of cloud computing and mobile computing technologies lead to the newly emerging mobile cloud com- puting paradigm.', u'Three major approaches have been pro- posed for mobile cloud applications: 1) extending the access to cloud services to mobile devices; 2) enabling mobile de- vices to work collaboratively as cloud resource providers; 3) augmenting the execution of mobile applications on portable devices using cloud resources.', u'In this paper, we focus on the third approach in supporting mobile data stream applica- tions.', u'More specifically, we study how to optimize the com- putation partitioning of a data stream application between mobile and cloud to achieve maximum speed/throughput in processing the streaming data.', u'We first propose a framework to provide runtime support for the dynamic computation partitioning and exe- cution of the application.']

        self.assertEqual(Summarize(article_title, article_text),
                         summarised_article_text)

    def test_short_article_returns_its_sentences(self):
        self.assertEqual(
            Summarize(u"A short article.", u"First sentence. Second sentence."),
            [u"First sentence.", u"Second sentence."],
        )


class TestGooseExtraction(TestCase):
    def test_extracts_article_from_raw_html_without_network(self):
        html = """<html lang="en"><head><title>Test article</title></head>
        <body><article>
          <p>This is a substantial first paragraph about Python compatibility, café culture, and article extraction.</p>
          <p>This is another substantial paragraph with enough useful words to pass the content filters.</p>
        </article></body></html>"""

        article = Goose({"enable_image_fetching": False}).extract(
            raw_html=html.encode("utf-8"))

        self.assertEqual(article.title, "Test article")
        self.assertIn("Python compatibility", article.cleaned_text)
        self.assertIn("café culture", article.cleaned_text)

    def test_summarize_url_with_mocked_response(self):
        html = b"""<html lang="en"><head><title>Example article title</title></head>
        <body><article>
          <p>Researchers announced a new discovery after years of careful work. The team shared detailed results with the public.</p>
          <p>Independent experts reviewed the findings and confirmed the core measurements. The discovery may lead to useful new technology.</p>
          <p>Further studies are planned for next year. Researchers said the work is still preliminary.</p>
        </article></body></html>"""

        with patch.object(HtmlFetcher, "get_html", return_value=html):
            summaries = SummarizeUrl("https://example.test/article")

        self.assertEqual(len(summaries), 5)
        self.assertTrue(all(isinstance(sentence, str) for sentence in summaries))

    def test_private_image_url_is_skipped_without_failing_extraction(self):
        html = """<html><head><title>Image fetch test</title></head><body><article>
          <p>This is a sufficiently long paragraph about article extraction, safe network handling, and testing.</p>
          <img src="http://127.0.0.1/private.jpg" alt="local image">
          <p>This is another sufficiently long paragraph so the body can be recognized correctly by Goose.</p>
        </article></body></html>"""

        article = Goose().extract(raw_html=html)

        self.assertEqual(article.title, "Image fetch test")
        self.assertIn("safe network handling", article.cleaned_text)


class TestNetworkPolicy(TestCase):
    def test_allows_public_http_url(self):
        self.assertEqual(validate_url("https://1.1.1.1/").scheme, "https")

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(ValueError):
            validate_url("file:///etc/passwd")

    def test_rejects_private_ip(self):
        with self.assertRaises(ValueError):
            validate_url("http://127.0.0.1/")

    @patch(
        "goose.network.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    def test_rejects_hostname_resolving_to_private_ip(self, getaddrinfo):
        with self.assertRaises(ValueError):
            validate_url("https://article.example/")
        getaddrinfo.assert_called_once()

    def test_redirect_handler_rejects_private_target(self):
        handler = SafeRedirectHandler()
        with self.assertRaises(ValueError):
            handler.redirect_request(
                Request("https://1.1.1.1/"), None, 302, "Found", {},
                "http://127.0.0.1/",
            )

    def test_read_limit_rejects_oversized_response(self):
        with self.assertRaises(ValueError):
            _read_limited(BytesIO(b"12345"), 4)

    @patch("goose.network.socket.create_connection")
    @patch(
        "goose.network.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 80))],
    )
    def test_http_connection_uses_the_validated_ip(self, getaddrinfo, create_connection):
        connection = _SafeHTTPConnection("article.example", 80, timeout=2)

        connection.connect()

        create_connection.assert_called_once_with(
            ("1.1.1.1", 80), timeout=2, source_address=None)
        getaddrinfo.assert_called_once()

    @patch("goose.network.build_opener")
    def test_fetch_bytes_applies_timeout_and_content_type(self, build_opener_mock):
        config = SimpleNamespace(
            browser_user_agent="PyTeaser test",
            request_timeout=2.5,
            allow_private_network=False,
        )
        response = MagicMock()
        response.__enter__.return_value = response
        response.geturl.return_value = "https://1.1.1.1/"
        response.headers.get_content_type.return_value = "text/html"
        response.read.return_value = b"page"
        opener = build_opener_mock.return_value
        opener.open.return_value = response

        content = fetch_bytes(
            config, "https://1.1.1.1/", 4, {"text/html"})

        self.assertEqual(content, b"page")
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 2.5)

    def test_fetches_from_loopback_when_explicitly_allowed(self):
        body = b"<html>local test</html>"

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)

        config = SimpleNamespace(
            browser_user_agent="PyTeaser test",
            request_timeout=2,
            allow_private_network=True,
        )
        url = "http://127.0.0.1:%s/" % server.server_port

        self.assertEqual(fetch_bytes(config, url, 1024, {"text/html"}), body)


if __name__ == '__main__':
    unittest_main()
