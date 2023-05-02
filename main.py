import asyncio
import platform

import aiohttp
import pymorphy2

import adapters
from text_tools import calculate_jaundice_rate, split_by_words


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def main():
    morph = pymorphy2.MorphAnalyzer()
    charged_words = ['чрезвычайно', 'фантастический']

    async with aiohttp.ClientSession() as session:
        html = await fetch(session, 'https://inosmi.ru/20211116/250914886.html')
        clean_text = adapters.SANITIZERS['inosmi_ru'](html, plaintext=True)
        article_words = split_by_words(morph, clean_text)
        jaundice_rating = calculate_jaundice_rate(article_words, charged_words)
        print(f'Рейтинг: {jaundice_rating}')
        print(f'Слов в статье: {len(article_words)}')


if __name__ == '__main__':
    if platform.system() == 'Windows':
        # Без этого возникает RuntimeError после окончания работы
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
