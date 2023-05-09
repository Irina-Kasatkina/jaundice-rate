from aiohttp import web

from articles_processor import process_articles


async def handle(request):
    urls = request.query.get('urls', '').split(',')
    results = await process_articles(urls)
    return web.json_response(results)


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    web.run_app(app)