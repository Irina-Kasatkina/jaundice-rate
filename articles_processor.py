import asyncio
import platform
from enum import Enum
from pathlib import Path

import pymorphy2
from aiohttp import ClientResponseError, ClientSession, InvalidURL
from anyio import sleep, create_task_group

from adapters import ArticleNotFound, SANITIZERS
from exceptions import DirectoryNotFound
from text_tools import calculate_jaundice_rate, split_by_words


LOG_FILENAME = 'log.txt'

charged_words = None
morph = None


class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'
    INVALID_URL = 'INVALID_URL'


def read_charged_words():
    charged_words_dirpath = Path().resolve() / 'data' / 'charged_dict'
    try:
        charged_words = []
        for charged_words_filepath in charged_words_dirpath.iterdir():
            if charged_words_filepath.is_file():
                with open(charged_words_filepath, 'r', encoding='utf-8') as charged_words_file:
                    charged_words.extend(charged_words_file.read().split())
        return charged_words
    except FileNotFoundError as ex:
        raise DirectoryNotFound(f'Не найдена папка с "заряженными" словами {charged_words_dirpath}')


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, url, results):
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
    except asyncio.TimeoutError:
        result['status'] = ProcessingStatus.TIMEOUT.value
    except TimeoutError:
        result['status'] = ProcessingStatus.TIMEOUT.value
    results.append(result)


async def process_articles(articles_urls):
    global morph
    if not morph:
        morph = pymorphy2.MorphAnalyzer()

    global charged_words
    if not charged_words:
        charged_words = read_charged_words()

    results = []
    async with ClientSession() as session:
        async with create_task_group() as task_group:
            for url in articles_urls:
                task_group.start_soon(process_article, session, url, results)
    return results


if __name__ == '__main__':
    if platform.system() == 'Windows':
        # Без этого возникает RuntimeError после окончания работы main()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    test_articles_urls = [
        'https://dvmn.org/media/filer_public/51/83/'
        '51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt',
        'https://lenta.ru/brief/2021/08/26/afg_terror/',
        'https://inosmi.ru/not/exist.html',
        'https://inosmi.ru/20211116/250914886.html',
        'https://inosmi.ru/20230504/ukraina-262710611.html',
        'https://inosmi.ru/20230504/nato-262692864.html',
        'https://inosmi.ru/20230505/konflikt-262704497.html',
        'https://inosmi.ru/20230505/ukraina-262724526.html',
    ]

    results = asyncio.run(process_articles(test_articles_urls))
    for result in results:
        print()
        for key, value in result.items():
            print(f'{key}: {value}') 
