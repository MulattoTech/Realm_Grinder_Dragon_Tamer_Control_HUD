"""Bounded offline Ruffle compatibility probe; never imports or edits saves.

Requires optional developer dependency playwright and an installed Edge browser.
Place a local game.swf and Ruffle's self-hosted files under ASSETS/ruffle first.
All downloads/provisioning are explicit; the probe permits only its own origin.
"""
import argparse
import asyncio
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import uuid
from urllib.parse import urlsplit


def runtime_errors(messages):
    # Ruffle emits Rust ERROR records through console.log, not console.error.
    return [m for m in messages if m['type'] in ('error', 'pageerror') or
            'Error running AVM2' in m['text'] or '%cERROR%c' in m['text']]


async def probe(assets, output, browser, seconds):
    from playwright.async_api import async_playwright
    assets = assets.resolve(strict=True)
    for name in ('game.swf', 'ruffle/ruffle.js'):
        if not (assets / name).is_file():
            raise FileNotFoundError(f'Missing local runtime input: {name}')
    output = output.resolve()
    if output == assets or assets in output.parents or output in assets.parents:
        raise ValueError('Private browser state must be separate from served assets')
    output.mkdir(parents=True, exist_ok=False)
    html = b'''<!doctype html><style>body{margin:0}ruffle-player{display:block;width:976px;height:669px}</style>
    <script src="ruffle/ruffle.js"></script><script>
    addEventListener('load',async()=>{try{
    const p=RufflePlayer.newest().createPlayer();document.body.appendChild(p);
    await p.ruffle(1).load({url:'game.swf',playerRuntime:'air',autoplay:'on',
    unmuteOverlay:'hidden',logLevel:'info',allowScriptAccess:false,
    allowNetworking:'internal',backgroundExecutionMode:'mainThread'});
    window.engineLoaded=true;}catch(e){console.error(String(e));}});</script>'''

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/':
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(html)
            elif path == '/game.swf' or (path.startswith('/ruffle/') and '..' not in path):
                super().do_GET()
            else:
                self.send_error(404)

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(assets)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    logs, blocked = [], []
    report = {'game_sha256': hashlib.sha256((assets/'game.swf').read_bytes()).hexdigest(),
              'gameplay_verified': False, 'save_imported': False}
    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(str(output/'profile'),
                executable_path=str(browser), headless=True, chromium_sandbox=True,
                service_workers='block', viewport={'width': 1000, 'height': 720})
            try:
                async def guard(route):
                    url = urlsplit(route.request.url)
                    if f'{url.scheme}://{url.netloc}' == origin:
                        await route.continue_()
                    else:
                        blocked.append(f'{url.scheme}://{url.netloc}{url.path}')
                        await route.abort()
                await context.route('**/*', guard)
                page = context.pages[0]
                page.on('console', lambda m: logs.append({'type': m.type, 'text': m.text}))
                page.on('pageerror', lambda e: logs.append({'type': 'pageerror', 'text': str(e)}))
                await page.goto(origin, wait_until='domcontentloaded', timeout=30000)
                await page.wait_for_timeout(seconds * 1000)
                report['engine_loaded'] = await page.evaluate('window.engineLoaded === true')
                await page.screenshot(path=str(output/'runtime.png'))
                report['runtime_errors'] = runtime_errors(logs)
                report['status'] = 'RUNTIME_ERROR' if report['runtime_errors'] else 'GAMEPLAY_NOT_VERIFIED'
            finally:
                await context.close()
    finally:
        server.shutdown()
        server.server_close()
        report.update(blocked_requests=blocked, console=logs)
        (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--browser', type=Path, default=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'))
    parser.add_argument('--seconds', type=int, choices=range(1, 61), default=15)
    args = parser.parse_args()
    output = args.assets.resolve().parent / ('runtime-probe-' + uuid.uuid4().hex)
    result = asyncio.run(probe(args.assets, output, args.browser, args.seconds))
    print(json.dumps({'output': str(output), 'status': result['status'],
                      'engine_loaded': result.get('engine_loaded'),
                      'runtime_errors': result.get('runtime_errors')}, indent=2))
