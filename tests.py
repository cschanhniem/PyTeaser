"""Offline tests for PyTeaser's text summarization API."""

from unittest import TestCase, main as unittest_main
from unittest.mock import patch

from goose import Goose
from goose.network import HtmlFetcher
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


if __name__ == '__main__':
    unittest_main()
