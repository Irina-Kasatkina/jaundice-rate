from aiohttp import web

from articles_processor import process_articles


MAX_COUNT_OF_URLS = 10


async def handle(request):
    urls = request.query.get('urls', '').split(',')
    if len(urls) > MAX_COUNT_OF_URLS:
        error_message = f'too many urls in request, should be {MAX_COUNT_OF_URLS} or less'
        return web.json_response({'error': error_message}, status=400)

    results = await process_articles(urls)
    return web.json_response(results)


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    web.run_app(app)
