import asyncio
import contextlib
import logging
import platform
import time
from enum import Enum
from pathlib import Path

import pymorphy2
from aiohttp import ClientResponseError, ClientSession
from anyio import sleep, create_task_group
from async_timeout import timeout

from adapters import ArticleNotFound, SANITIZERS
from exceptions import DirectoryNotFound
from text_tools import calculate_jaundice_rate, split_by_words


LOG_FILENAME = 'log.txt'
TEST_ARTICLES = [
    'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt',
    'https://lenta.ru/brief/2021/08/26/afg_terror/',
    'https://inosmi.ru/not/exist.html',
    'https://inosmi.ru/20211116/250914886.html',
    'https://inosmi.ru/20230504/ukraina-262710611.html',
    'https://inosmi.ru/20230504/nato-262692864.html',
    'https://inosmi.ru/20230505/konflikt-262704497.html',
    'https://inosmi.ru/20230505/ukraina-262724526.html',
]

class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'

@contextlib.contextmanager
def log_execution_time():
    start_time = time.monotonic()
    try:
        yield
    finally:
        execution_time = time.monotonic() - start_time
        logging.info(f'Анализ закончен за {execution_time:.2f} сек')


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


async def process_article(session, morph, charged_words, url, results):
    result = {'URL:': url, 'Статус:': None, 'Рейтинг:': None, 'Слов в статье:': None}
    try:
        html = await fetch(session, url)
        if url == 'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt':
            clean_text = html
        else:
            clean_text = SANITIZERS['inosmi_ru'](html, plaintext=True)

        with log_execution_time():
            article_words = split_by_words(morph, clean_text)

        result['Статус:'] = ProcessingStatus.OK.value
        result['Рейтинг:'] = calculate_jaundice_rate(article_words, charged_words)
        result['Слов в статье:'] = len(article_words)
        with open(LOG_FILENAME, 'r') as log_file:
           result['INFO:root:Анализ закончен за'] = f'{log_file.read().split()[-2]} сек'
    except ClientResponseError:
        result['Статус:'] = ProcessingStatus.FETCH_ERROR.value
    except ArticleNotFound:
        result['Статус:'] = ProcessingStatus.PARSING_ERROR.value
    except asyncio.TimeoutError:
        result['Статус:'] = ProcessingStatus.TIMEOUT.value

    results.append(result)


async def main():
    morph = pymorphy2.MorphAnalyzer()
    charged_words = read_charged_words()
    results = []

    async with ClientSession() as session:
        async with create_task_group() as task_group:
            for url in TEST_ARTICLES:
                task_group.start_soon(process_article, session, morph, charged_words, url, results)

    for result in results:
        print()
        for key, value in result.items():
            print(key, value)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, filename=LOG_FILENAME, filemode='w')

    if platform.system() == 'Windows':
        # Без этого возникает RuntimeError после окончания работы main()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
