import asyncio
import platform
from pathlib import Path

import aiohttp
import pymorphy2
from aiohttp import ClientResponseError
from anyio import sleep, create_task_group

import adapters
from exceptions import DirectoryNotFound
from text_tools import calculate_jaundice_rate, split_by_words


TEST_ARTICLES = [
    'https://inosmi.ru/not/exist.html',
    'https://inosmi.ru/20211116/250914886.html',
    'https://inosmi.ru/20230504/ukraina-262710611.html',
    'https://inosmi.ru/20230504/nato-262692864.html',
    'https://inosmi.ru/20230505/konflikt-262704497.html',
    'https://inosmi.ru/20230505/ukraina-262724526.html',
]


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
    result = {'URL:': url}
    try:
        html = await fetch(session, url)
        clean_text = adapters.SANITIZERS['inosmi_ru'](html, plaintext=True)
        article_words = split_by_words(morph, clean_text)
        result['Статус:'] = 'OK'
        result['Рейтинг:'] = calculate_jaundice_rate(article_words, charged_words)
        result['Слов в статье:'] = len(article_words)
    except ClientResponseError:
        result['Статус:'] = 'FETCH_ERROR'
        result['Рейтинг:'] = 'None'
        result['Слов в статье:'] = 'None'

    results.append(result)


async def main():
    morph = pymorphy2.MorphAnalyzer()
    charged_words = read_charged_words()
    results = []

    async with aiohttp.ClientSession() as session:
        async with create_task_group() as task_group:
            for url in TEST_ARTICLES:
                task_group.start_soon(process_article, session, morph, charged_words, url, results)

    for result in results:
        print()
        for key, value in result.items():
            print(key, value)


if __name__ == '__main__':
    if platform.system() == 'Windows':
        # Без этого возникает RuntimeError после окончания работы
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
