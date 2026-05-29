# coding=utf-8
from collections import Counter
from math import fabs
from re import search as regex_search, sub as regex_sub, UNICODE as REGEX_UNICODE

stopWords = set([
    "-", " ", ",", ".", "a", "e", "i", "o", "u", "t", "about", "above",
    "above", "across", "after", "afterwards", "again", "against", "all",
    "almost", "alone", "along", "already", "also", "although", "always",
    "am", "among", "amongst", "amoungst", "amount", "an", "and",
    "another", "any", "anyhow", "anyone", "anything", "anyway",
    "anywhere", "are", "around", "as", "at", "back", "be", "became",
    "because", "become", "becomes", "becoming", "been", "before",
    "beforehand", "behind", "being", "below", "beside", "besides",
    "between", "beyond", "both", "bottom", "but", "by", "call", "can",
    "cannot", "can't", "co", "con", "could", "couldn't", "de",
    "describe", "detail", "did", "do", "done", "down", "due", "during",
    "each", "eg", "eight", "either", "eleven", "else", "elsewhere",
    "empty", "enough", "etc", "even", "ever", "every", "everyone",
    "everything", "everywhere", "except", "few", "fifteen", "fifty",
    "fill", "find", "fire", "first", "five", "for", "former",
    "formerly", "forty", "found", "four", "from", "front", "full",
    "further", "get", "give", "go", "got", "had", "has", "hasnt",
    "have", "he", "hence", "her", "here", "hereafter", "hereby",
    "herein", "hereupon", "hers", "herself", "him", "himself", "his",
    "how", "however", "hundred", "i", "ie", "if", "in", "inc", "indeed",
    "into", "is", "it", "its", "it's", "itself", "just", "keep", "last",
    "latter", "latterly", "least", "less", "like", "ltd", "made", "make",
    "many", "may", "me", "meanwhile", "might", "mill", "mine", "more",
    "moreover", "most", "mostly", "move", "much", "must", "my", "myself",
    "name", "namely", "neither", "never", "nevertheless", "new", "next",
    "nine", "no", "nobody", "none", "noone", "nor", "not", "nothing",
    "now", "nowhere", "of", "off", "often", "on", "once", "one", "only",
    "onto", "or", "other", "others", "otherwise", "our", "ours",
    "ourselves", "out", "over", "own", "part", "people", "per",
    "perhaps", "please", "put", "rather", "re", "said", "same", "see",
    "seem", "seemed", "seeming", "seems", "several", "she", "should",
    "show", "side", "since", "sincere", "six", "sixty", "so", "some",
    "somehow", "someone", "something", "sometime", "sometimes",
    "somewhere", "still", "such", "take", "ten", "than", "that", "the",
    "their", "them", "themselves", "then", "thence", "there",
    "thereafter", "thereby", "therefore", "therein", "thereupon",
    "these", "they", "thickv", "thin", "third", "this", "those",
    "though", "three", "through", "throughout", "thru", "thus", "to",
    "together", "too", "top", "toward", "towards", "twelve", "twenty",
    "two", "un", "under", "until", "up", "upon", "us", "use", "very",
    "via", "want", "was", "we", "well", "were", "what", "whatever",
    "when", "whence", "whenever", "where", "whereafter", "whereas",
    "whereby", "wherein", "whereupon", "wherever", "whether", "which",
    "while", "whither", "who", "whoever", "whole", "whom", "whose",
    "why", "will", "with", "within", "without", "would", "yet", "you",
    "your", "yours", "yourself", "yourselves", "the",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    "1", "10", "2012", "sa", "says", "pm",
    "2013", "na", "ng", "ang", "year", "years", "percent", "ko", "ako",
    "yung", "yun", "2", "3", "4", "5", "6", "7", "8", "9", "0", "time",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
])
ideal = 20.0
TITLE_WEIGHT = 1.5
FREQUENCY_WEIGHT = 2.0
LENGTH_WEIGHT = 1.0
POSITION_WEIGHT = 1.0
_SENTENCE_PUNCTUATION = ".!?。！？؟।"
_CLOSING_PUNCTUATION = "\"'”’»)]}"
_NO_SPACE_SENTENCE_PUNCTUATION = "!?。！？؟।"
_TITLE_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "rev", "sr", "jr", "st",
}
_NONTERMINAL_ABBREVIATIONS = {"e.g", "i.e", "n.b"}
_CONTEXTUAL_ABBREVIATIONS = {
    "a.m", "p.m", "u.s", "u.k", "u.n", "etc", "vs", "inc", "ltd",
    "corp", "co", "approx", "fig", "no", "vol", "jan", "feb", "mar",
    "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}


def SummarizeUrl(url, sentence_count=5):
    sentence_count = _validate_sentence_count(sentence_count)
    summaries = []
    try:
        article = grab_link(url)
    except IOError:
        return None

    if not (article and article.cleaned_text and article.title):
        return None

    summaries = Summarize(
        str(article.title), str(article.cleaned_text), sentence_count)
    return summaries


def Summarize(title, text, sentence_count=5):
    """Return an extractive summary for a title and article text.

    Text arguments may be strings or UTF-8 encoded bytes. A missing title is
    treated as an empty string; blank article text produces an empty summary.
    """
    sentence_count = _validate_sentence_count(sentence_count)
    title = _coerce_text(title, "title", allow_none=True)
    text = _coerce_text(text, "text")
    if not text.strip():
        return []
    if sentence_count == 0:
        return []

    sentences = split_sentences(text)
    if not sentences:
        return []
    keys = keywords(text)
    titleWords = split_words(title)

    # Rank each occurrence separately, select the best sentences, then restore
    # the article's original order for a coherent extractive summary.
    ranked = sorted(
        score(sentences, titleWords, keys),
        key=lambda result: (-result[2], result[0]),
    )
    selected = _select_non_redundant(ranked, sentence_count)
    selected.sort(key=lambda result: result[0])
    return [sentence for _, sentence, _ in selected]


def _coerce_text(value, name, allow_none=False):
    if value is None and allow_none:
        return ""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("%s must contain valid UTF-8" % name) from error
    if not isinstance(value, str):
        raise TypeError("%s must be a string or UTF-8 bytes" % name)
    return value


def _validate_sentence_count(sentence_count):
    if isinstance(sentence_count, bool) or not isinstance(sentence_count, int):
        raise TypeError("sentence_count must be a non-negative integer")
    if sentence_count < 0:
        raise ValueError("sentence_count must be a non-negative integer")
    return sentence_count


def _select_non_redundant(ranked, sentence_count, threshold=0.8):
    """Select high-ranked sentences while avoiding excessive word overlap."""
    selected = []
    selected_terms = []
    selected_text = set()
    for candidate in ranked:
        words = split_words(candidate[1])
        normalized_text = " ".join(words) or candidate[1].strip().casefold()
        if normalized_text in selected_text:
            continue

        terms = set(words)
        content_terms = terms.difference(stopWords)
        if content_terms:
            terms = content_terms

        if (len(terms) >= 3 and any(
                len(existing) >= 3
                and _jaccard_similarity(terms, existing) >= threshold
                for existing in selected_terms)):
            continue

        selected.append(candidate)
        selected_terms.append(terms)
        selected_text.add(normalized_text)
        if len(selected) == sentence_count:
            break
    return selected


def _jaccard_similarity(left, right):
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / float(len(union))


def grab_link(inurl):
    #extract article information using Python Goose
    from goose import Goose
    try:
        article = Goose().extract(url=inurl)
        return article
    except ValueError:
        return None
    return None


def score(sentences, titleWords, keywords):
    """Return ``(index, sentence, score)`` for every sentence occurrence."""
    senSize = len(sentences)
    ranks = []
    for i, s in enumerate(sentences):
        sentence = split_words(s)
        titleFeature = title_score(titleWords, sentence)
        sentenceLength = length_score(sentence)
        sentencePosition = sentence_position(i+1, senSize)
        sbsFeature = sbs(sentence, keywords)
        dbsFeature = dbs(sentence, keywords)
        frequency = (sbsFeature + dbsFeature) / 2.0 * 10.0

        totalWeight = (
            TITLE_WEIGHT + FREQUENCY_WEIGHT + LENGTH_WEIGHT + POSITION_WEIGHT)
        totalScore = (
            titleFeature * TITLE_WEIGHT
            + frequency * FREQUENCY_WEIGHT
            + sentenceLength * LENGTH_WEIGHT
            + sentencePosition * POSITION_WEIGHT
        ) / totalWeight
        ranks.append((i, s, totalScore))
    return ranks


def sbs(words, keywords):
    score = 0.0
    if len(words) == 0:
        return 0
    for word in words:
        if word in keywords:
            score += keywords[word]
    return (1.0 / fabs(len(words)) * score)/10.0


def dbs(words, keywords):
    if (len(words) == 0):
        return 0

    summ = 0
    first = []
    second = []

    for i, word in enumerate(words):
        if word in keywords:
            score = keywords[word]
            if first == []:
                first = [i, score]
            else:
                second = first
                first = [i, score]
                dif = first[0] - second[0]
                summ += (first[1]*second[1]) / (dif ** 2)

    # number of intersections
    k = len(set(keywords.keys()).intersection(set(words))) + 1
    return (1/(k*(k+1.0))*summ)


def split_words(text):
    #split a string into array of words
    text = _coerce_text(text, "text")
    text = regex_sub(r'[^\w ]', '', text, flags=REGEX_UNICODE)  # strip special chars
    return [x.strip('.').lower() for x in text.split()]


def keywords(text):
    """get the top 10 keywords and their frequency scores
    ignores blacklisted words in stopWords,
    counts the number of occurrences of each word
    """
    text = split_words(text)
    numWords = len(text)  # of words before removing blacklist words
    freq = Counter(x for x in text if x not in stopWords)

    minSize = min(10, len(freq))  # get first 10
    keywords = {x: y for x, y in freq.most_common(minSize)}  # recreate a dict

    for k in keywords:
        articleScore = keywords[k]*1.0 / numWords
        keywords[k] = articleScore * 1.5 + 1

    return keywords


def split_sentences(text):
    """Split text into sentences while preserving punctuation and source order."""
    text = _coerce_text(text, "text")
    if not text.strip():
        return []

    sentences = []
    paragraphs = regex_sub(r"\n\s*\n+", "\n\n", text.strip()).split("\n\n")
    for paragraph in paragraphs:
        paragraph = regex_sub(r"\s+", " ", paragraph, flags=REGEX_UNICODE).strip()
        if not paragraph:
            continue

        start = 0
        index = 0
        while index < len(paragraph):
            if paragraph[index] not in _SENTENCE_PUNCTUATION:
                index += 1
                continue

            punctuation_start = index
            while (index < len(paragraph)
                   and paragraph[index] in _SENTENCE_PUNCTUATION):
                index += 1
            punctuation_end = index
            while (index < len(paragraph)
                   and paragraph[index] in _CLOSING_PUNCTUATION):
                index += 1

            punctuation = paragraph[punctuation_start:punctuation_end]
            at_end = index == len(paragraph)
            has_whitespace = not at_end and paragraph[index].isspace()
            no_space_boundary = any(
                mark in punctuation for mark in _NO_SPACE_SENTENCE_PUNCTUATION)
            if not (at_end or has_whitespace or no_space_boundary):
                continue

            if ("." in punctuation
                    and not no_space_boundary
                    and not _should_split_after_period(
                        paragraph, punctuation_start, index)):
                continue

            sentence = paragraph[start:index].strip()
            if sentence:
                sentences.append(sentence)
            start = index
            while start < len(paragraph) and paragraph[start].isspace():
                start += 1
            index = start

        trailing_text = paragraph[start:].strip()
        if trailing_text:
            sentences.append(trailing_text)

    return sentences


def _should_split_after_period(text, punctuation_start, boundary_end):
    match = regex_search(
        r"([^\W_]+(?:\.[^\W_]+)*)$",
        text[:punctuation_start],
        flags=REGEX_UNICODE,
    )
    if not match:
        return True

    abbreviation = match.group(1).casefold()
    if abbreviation in _TITLE_ABBREVIATIONS | _NONTERMINAL_ABBREVIATIONS:
        return False

    next_word = regex_search(
        r"\w+", text[boundary_end:], flags=REGEX_UNICODE)
    next_initial = next_word.group(0)[0] if next_word else ""
    if abbreviation in _CONTEXTUAL_ABBREVIATIONS:
        return not next_initial or next_initial.isupper()

    if (len(abbreviation) == 1 and abbreviation.isalpha()
            and next_initial.isupper()):
        return False
    return True



def length_score(sentence):
    return max(0.0, 1.0 - fabs(ideal - len(sentence)) / ideal)


def title_score(title, sentence):
    title_terms = {word for word in title if word not in stopWords}
    if not title_terms:
        return 0.0

    sentence_terms = {word for word in sentence if word not in stopWords}
    return len(title_terms.intersection(sentence_terms)) / float(len(title_terms))


def sentence_position(i, size):
    """different sentence positions indicate different
    probability of being an important sentence"""

    normalized = i*1.0 / size
    if 0 < normalized <= 0.1:
        return 0.17
    elif 0.1 < normalized <= 0.2:
        return 0.23
    elif 0.2 < normalized <= 0.3:
        return 0.14
    elif 0.3 < normalized <= 0.4:
        return 0.08
    elif 0.4 < normalized <= 0.5:
        return 0.05
    elif 0.5 < normalized <= 0.6:
        return 0.04
    elif 0.6 < normalized <= 0.7:
        return 0.06
    elif 0.7 < normalized <= 0.8:
        return 0.04
    elif 0.8 < normalized <= 0.9:
        return 0.04
    elif 0.9 < normalized <= 1.0:
        return 0.15
    else:
        return 0
