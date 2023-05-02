import asyncio
import platform

import aiohttp


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def main():
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, 'https://inosmi.ru/20211116/250914886.html')
        print(html)


if __name__ == '__main__':
    if platform.system() == 'Windows':
        # Без этого возникает RuntimeError после окончания работы
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(main())
