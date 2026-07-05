"""Offline tests for PyTeaser's text summarization API."""

import socket
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main as unittest_main
from unittest.mock import MagicMock, patch
from urllib.request import Request

from goose import Goose
from goose.article import Article
from goose.configuration import Configuration
from goose.crawler import Crawler
from goose.extractors import StandardContentExtractor
from goose.network import HtmlFetcher
from goose.network import (
    SafeRedirectHandler,
    _SafeHTTPConnection,
    _read_limited,
    fetch_bytes,
    validate_url,
)
from pyteaser import (
    Summarize,
    SummarizeUrl,
    keywords,
    length_score,
    score,
    split_sentences,
    split_words,
    summarize,
    summarize_url,
    stopWords,
    title_score,
)


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

    def test_blank_text_returns_empty_summary(self):
        self.assertEqual(Summarize("Title", " \n\t "), [])

    def test_missing_title_and_utf8_bytes_are_supported(self):
        self.assertEqual(Summarize(None, "First sentence. Second sentence."), [
            "First sentence.",
            "Second sentence.",
        ])
        self.assertEqual(Summarize("Café".encode("utf-8"), "Café matters.".encode("utf-8")), [
            "Café matters.",
        ])

    def test_pep8_text_api_matches_legacy_name(self):
        text = "Researchers announced a discovery. Experts reviewed the evidence."
        self.assertEqual(
            summarize("Discovery", text, sentence_count=1),
            Summarize("Discovery", text, sentence_count=1),
        )

    def test_unsupported_text_types_raise_clear_errors(self):
        with self.assertRaisesRegex(TypeError, "text must be a string"):
            Summarize("Title", None)
        with self.assertRaisesRegex(TypeError, "text must be a string"):
            Summarize("Title", 42)
        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            Summarize("Title", b"\xff")

    def test_sentence_count_is_configurable(self):
        text = "One sentence. Two sentence. Three sentence. Four sentence. Five sentence. Six sentence."

        self.assertEqual(len(Summarize("Title", text)), 5)
        self.assertEqual(len(Summarize("Title", text, sentence_count=2)), 2)
        self.assertEqual(Summarize("Title", text, sentence_count=0), [])

    def test_invalid_sentence_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "sentence_count"):
            Summarize("Title", "Article text.", sentence_count=-1)
        with self.assertRaisesRegex(TypeError, "sentence_count"):
            Summarize("Title", "Article text.", sentence_count=1.5)
        with self.assertRaisesRegex(TypeError, "sentence_count"):
            Summarize("Title", "Article text.", sentence_count=True)

    def test_sentence_splitter_handles_lowercase_starts_and_quotes(self):
        self.assertEqual(
            split_sentences("First ends. lowercase follows! “Quoted?” yes."),
            ["First ends.", "lowercase follows!", "“Quoted?”", "yes."],
        )

    def test_sentence_splitter_handles_abbreviations_and_decimals(self):
        self.assertEqual(
            split_sentences(
                "Dr. Smith paid 3.14 dollars. The U.S. team met at 5 p.m. It continued."
            ),
            [
                "Dr. Smith paid 3.14 dollars.",
                "The U.S. team met at 5 p.m.",
                "It continued.",
            ],
        )

    def test_sentence_splitter_keeps_number_abbreviations_together(self):
        self.assertEqual(
            split_sentences("She chose No. 3. It worked."),
            ["She chose No. 3.", "It worked."],
        )

    def test_sentence_splitter_handles_paragraphs_and_cjk_punctuation(self):
        self.assertEqual(
            split_sentences("First paragraph\n\n这是第一句。这是第二句！"),
            ["First paragraph", "这是第一句。", "这是第二句！"],
        )

    def test_summary_restores_original_order_after_ranking(self):
        sentences = [
            "Alpha begins today.",
            "Bravo announces plans.",
            "Charlie discovers evidence.",
            "Delta publishes results.",
            "Echo reports success.",
            "Foxtrot reveals details.",
        ]
        ranked = [
            (5, sentences[5], 10.0),
            (1, sentences[1], 9.0),
            (4, sentences[4], 8.0),
            (2, sentences[2], 7.0),
            (3, sentences[3], 6.0),
            (0, sentences[0], 1.0),
        ]

        with patch("pyteaser.score", return_value=ranked):
            summary = Summarize("An article", " ".join(sentences))

        self.assertEqual(summary, sentences[1:])

    def test_summary_skips_redundant_sentences(self):
        sentences = [
            "Researchers confirmed several new findings.",
            "Researchers confirmed several new findings.",
            "The final report described four separate outcomes.",
            "Independent experts reviewed the published evidence.",
        ]
        ranked = [
            (0, sentences[0], 10.0),
            (1, sentences[1], 9.0),
            (3, sentences[3], 8.0),
            (2, sentences[2], 7.0),
        ]

        with patch("pyteaser.score", return_value=ranked):
            summary = Summarize("An article", " ".join(sentences), sentence_count=3)

        self.assertEqual(summary, [sentences[0], sentences[2], sentences[3]])

    def test_short_article_does_not_repeat_duplicate_sentences(self):
        self.assertEqual(
            Summarize(
                "A short article",
                "Researchers confirmed several findings. Researchers confirmed several findings.",
            ),
            ["Researchers confirmed several findings."],
        )

    def test_topic_words_are_not_filtered_as_stopwords(self):
        self.assertNotIn("government", stopWords)
        self.assertNotIn("police", stopWords)
        self.assertNotIn("reuters", stopWords)
        self.assertNotIn("rappler", stopWords)
        self.assertIn("government", keywords("Government police"))
        self.assertIn("police", keywords("Government police"))

    def test_language_specific_stopwords_are_used(self):
        spanish_keywords = keywords(
            "El gobierno anuncia una nueva reforma", language="es")

        self.assertNotIn("el", spanish_keywords)
        self.assertNotIn("una", spanish_keywords)
        self.assertIn("gobierno", spanish_keywords)
        self.assertIn("reforma", spanish_keywords)

    def test_chinese_tokenizer_is_used_when_available(self):
        jieba = ModuleType("jieba")
        jieba.cut = lambda text: ["研究者", "公布", "新发现", "。"]

        with patch.dict("sys.modules", {"jieba": jieba}):
            words = split_words("研究者公布新发现。", language="zh")

        self.assertEqual(words, ["研究者", "公布", "新发现"])

    def test_unsupported_language_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported language"):
            Summarize("Title", "Article text.", language="xx")

    def test_length_score_is_bounded(self):
        self.assertEqual(length_score(["word"] * 20), 1.0)
        self.assertEqual(length_score(["word"] * 40), 0.0)
        self.assertEqual(length_score(["word"] * 100), 0.0)

    def test_repeated_title_words_do_not_inflate_title_relevance(self):
        self.assertEqual(
            title_score(["government", "government"], ["government"] * 4),
            1.0,
        )

    def test_score_preserves_repeated_sentence_occurrences(self):
        repeated = "Repeated sentence."

        ranked = score([repeated, repeated], [], {})

        self.assertEqual([result[0] for result in ranked], [0, 1])
        self.assertEqual([result[1] for result in ranked], [repeated, repeated])


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

    def test_summarize_url_honors_sentence_count(self):
        html = b"""<html lang="en"><head><title>Example article title</title></head>
        <body><article><p>One sentence is here. Two sentence is here. Three sentence is here.
        Four sentence is here. Five sentence is here. Six sentence is here.</p></article></body></html>"""

        with patch.object(HtmlFetcher, "get_html", return_value=html):
            summaries = SummarizeUrl(
                "https://example.test/article", sentence_count=2)

        self.assertEqual(len(summaries), 2)

    def test_summarize_url_uses_article_language_metadata(self):
        article = SimpleNamespace(
            title="Articulo de ejemplo",
            cleaned_text="El gobierno anuncia una nueva reforma.",
            meta_lang="es",
        )

        with patch("pyteaser.grab_link", return_value=article):
            with patch("pyteaser.Summarize", return_value=["resumen"]) as summarize:
                result = SummarizeUrl("https://example.test/articulo")

        self.assertEqual(result, ["resumen"])
        self.assertEqual(summarize.call_args.kwargs["language"], "es")

    def test_pep8_url_api_forwards_options(self):
        article = SimpleNamespace(
            title="Example article",
            cleaned_text="Researchers announced a discovery. Experts reviewed evidence.",
            meta_lang="en",
        )

        with patch("pyteaser.grab_link", return_value=article):
            summaries = summarize_url(
                "https://example.test/article", sentence_count=1)

        self.assertEqual(len(summaries), 1)

    def test_private_image_url_is_skipped_without_failing_extraction(self):
        html = """<html><head><title>Image fetch test</title></head><body><article>
          <p>This is a sufficiently long paragraph about article extraction, safe network handling, and testing.</p>
          <img src="http://127.0.0.1/private.jpg" alt="local image">
          <p>This is another sufficiently long paragraph so the body can be recognized correctly by Goose.</p>
        </article></body></html>"""

        article = Goose({"enable_image_fetching": True}).extract(raw_html=html)

        self.assertEqual(article.title, "Image fetch test")
        self.assertIn("safe network handling", article.cleaned_text)

    def test_image_fetching_is_disabled_by_default(self):
        html = """<html><head><title>No image fetch</title></head><body><article>
          <p>This is a sufficiently long paragraph about ordinary article extraction and summaries.</p>
          <img src="https://1.1.1.1/image.jpg" alt="remote image">
          <p>This second sufficiently long paragraph provides another useful extraction candidate.</p>
        </article></body></html>"""

        with patch.object(Crawler, "get_image_extractor") as get_image_extractor:
            article = Goose().extract(raw_html=html)

        get_image_extractor.assert_not_called()
        self.assertEqual(article.title, "No image fetch")


class TestGooseLanguageSelection(TestCase):
    def test_metadata_language_is_used_for_content_scoring(self):
        config = Configuration()
        article = Article()
        article.meta_lang = "es-MX"
        extractor = StandardContentExtractor(config)
        extractor.nodes_to_check = lambda doc: []

        extractor.calculate_best_node(article)

        self.assertEqual(extractor.language, "es")

    def test_configured_language_overrides_metadata_when_forced(self):
        config = Configuration()
        config.use_meta_language = False
        config.target_language = "fr"
        article = Article()
        article.meta_lang = "es"
        extractor = StandardContentExtractor(config)

        self.assertEqual(extractor.get_language(article), "fr")


class TestGooseInitialization(TestCase):
    def test_concurrent_initialization_uses_unique_write_probes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            storage_path = os.path.join(temporary_directory, "nested", "goose")
            config = SimpleNamespace(local_storage_path=storage_path)

            with ThreadPoolExecutor(max_workers=8) as executor:
                instances = list(executor.map(lambda _: Goose(config), range(16)))

            self.assertEqual(len(instances), 16)
            self.assertTrue(os.path.isdir(storage_path))
            self.assertFalse(os.path.exists(os.path.join(storage_path, "test.txt")))


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
