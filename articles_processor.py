import asyncio
import contextlib
from enum import Enum
from pathlib import Path

import pymorphy2
import pytest
from aiohttp import ClientResponseError, ClientSession, InvalidURL
from anyio import sleep, create_task_group

from adapters import ArticleNotFound, SANITIZERS
from text_tools import calculate_jaundice_rate, split_by_words


charged_words = []
morph = None


class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'
    INVALID_URL = 'INVALID_URL'


def fill_charged_words():
    global charged_words
    if not charged_words:
        charged_words = []
        with contextlib.suppress(FileNotFoundError):
            charged_words_dirpath = Path().resolve() / 'data' / 'charged_dict'
            for charged_words_filepath in charged_words_dirpath.iterdir():
                if charged_words_filepath.is_file():
                    with open(charged_words_filepath, 'r', encoding='utf-8') as charged_words_file:
                        charged_words.extend(charged_words_file.read().split())


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, url, results):
    global charged_words
    result = {'status': None, 'url': url, 'score': None, 'words_count': None}
    try:
        html = await fetch(session, url)
        if len(url) > 4 and url[-4:] == '.txt':
            clean_text = html
        else:
            clean_text = SANITIZERS['inosmi_ru'](html, plaintext=True)

        article_words = await split_by_words(morph, clean_text)
        result['status'] = ProcessingStatus.OK.value
        result['score'] = calculate_jaundice_rate(article_words, charged_words)
        result['words_count'] = len(article_words)
    except (ClientResponseError, InvalidURL):
        result['status'] = ProcessingStatus.FETCH_ERROR.value
    except ArticleNotFound:
        result['status'] = ProcessingStatus.PARSING_ERROR.value
    except (asyncio.TimeoutError, TimeoutError):
        result['status'] = ProcessingStatus.TIMEOUT.value
    results.append(result)


async def process_articles(articles_urls):
    global morph
    if not morph:
        morph = pymorphy2.MorphAnalyzer()

    fill_charged_words()

    results = []
    async with ClientSession() as session:
        async with create_task_group() as task_group:
            for url in articles_urls:
                task_group.start_soon(process_article, session, url, results)
    return results


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    # from https://github.com/pytest-dev/pytest-asyncio/issues/371
    policy = asyncio.WindowsSelectorEventLoopPolicy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    res._close = res.close
    res.close = lambda: None
    yield res
    res._close()


@pytest.mark.asyncio
async def test_process_article():
    global morph
    if not morph:
        morph = pymorphy2.MorphAnalyzer()

    fill_charged_words()

    async with ClientSession() as session:
        # OK
        results = []
        url = 'https://inosmi.ru/20211116/250914886.html'
        await process_article(session, url, results)
        assert len(results) == 1
        result = results[0]
        assert result['status'] == ProcessingStatus.OK.value
        assert result['url'] == url
        assert result['score'] >= 0
        assert result['score'] <= 100
        assert result['words_count'] > 0

        # Ошибка скачивания статьи
        results = []
        url = 'https://inosmi.ru/not/exist.html'
        await process_article(session, url, results)
        assert len(results) == 1
        result = results[0]
        assert result['status'] == ProcessingStatus.FETCH_ERROR.value
        assert result['url'] == url
        assert result['score'] is None
        assert result['words_count'] is None

        # Ошибка парсинга статьи
        results = []
        url = 'https://lenta.ru/brief/2021/08/26/afg_terror/'
        await process_article(session, url, results)
        assert len(results) == 1
        result = results[0]
        assert result['status'] == ProcessingStatus.PARSING_ERROR.value
        assert result['url'] == url
        assert result['score'] is None
        assert result['words_count'] is None

        # Ошибка Timeout
        results = []
        url = (
            'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b'
            '-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt'
        )
        await process_article(session, url, results)
        assert len(results) == 1
        result = results[0]
        assert result['status'] == ProcessingStatus.TIMEOUT.value
        assert result['url'] == url
        assert result['score'] is None
        assert result['words_count'] is None
