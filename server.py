from aiohttp import web


async def handle(request):
    urls = request.query.get('urls', '')
    response = {'urls': urls.split()}
    return web.json_response(response)


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    web.run_app(app)