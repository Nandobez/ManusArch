"""
Browser Server - Mantém browser aberto e recebe comandos via HTTP
Roda DENTRO do container
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

# Variáveis globais para o browser
playwright = None
browser = None
page = None


def init_browser():
    """Inicializa o browser"""
    global playwright, browser, page

    if browser is None:
        playwright = sync_playwright().start()
        browser = playwright.firefox.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1200, "height": 700})
        print("Browser iniciado!")

    return page


def execute_command(cmd: dict) -> dict:
    """Executa um comando no browser"""
    global page

    action = cmd.get("action", "")
    params = cmd.get("params", {})

    try:
        if page is None:
            init_browser()

        if action == "goto":
            url = params.get("url", "")
            page.goto(url, wait_until="domcontentloaded")
            return {"success": True, "title": page.title(), "url": page.url}

        elif action == "click":
            selector = params.get("selector", "")
            page.click(selector)
            return {"success": True, "message": f"Clicked {selector}"}

        elif action == "type":
            selector = params.get("selector", "")
            text = params.get("text", "")
            page.fill(selector, text)
            return {"success": True, "message": f"Typed in {selector}"}

        elif action == "press":
            key = params.get("key", "Enter")
            page.keyboard.press(key)
            return {"success": True, "message": f"Pressed {key}"}

        elif action == "screenshot":
            path = params.get("path", "/workspace/screenshot.png")
            page.screenshot(path=path)
            return {"success": True, "path": path}

        elif action == "get_text":
            selector = params.get("selector", "body")
            text = page.inner_text(selector)
            return {"success": True, "text": text[:5000]}  # Limita tamanho

        elif action == "get_html":
            selector = params.get("selector", "body")
            html = page.inner_html(selector)
            return {"success": True, "html": html[:5000]}

        elif action == "wait":
            ms = params.get("ms", 1000)
            page.wait_for_timeout(ms)
            return {"success": True, "message": f"Waited {ms}ms"}

        elif action == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 500)
            if direction == "down":
                page.evaluate(f"window.scrollBy(0, {amount})")
            else:
                page.evaluate(f"window.scrollBy(0, -{amount})")
            return {"success": True, "message": f"Scrolled {direction}"}

        elif action == "wait_for":
            selector = params.get("selector", "")
            timeout = params.get("timeout", 10000)
            try:
                page.wait_for_selector(selector, timeout=timeout)
                return {"success": True, "message": f"Element {selector} found"}
            except:
                return {"success": False, "error": f"Timeout waiting for {selector}"}

        elif action == "get_all_text":
            selector = params.get("selector", "")
            elements = page.query_selector_all(selector)
            texts = [el.inner_text() for el in elements[:20]]  # Limita a 20
            return {"success": True, "texts": texts, "count": len(texts)}

        elif action == "get_attribute":
            selector = params.get("selector", "")
            attribute = params.get("attribute", "href")
            element = page.query_selector(selector)
            if element:
                value = element.get_attribute(attribute)
                return {"success": True, "value": value}
            return {"success": False, "error": "Element not found"}

        elif action == "scroll_to_comments":
            # Scroll específico para carregar comentários do YouTube
            page.evaluate("window.scrollTo(0, 800)")
            page.wait_for_timeout(2000)
            page.evaluate("window.scrollTo(0, 1200)")
            page.wait_for_timeout(3000)
            return {"success": True, "message": "Scrolled to comments section"}

        elif action == "get_youtube_comments":
            # Extrai comentários do YouTube usando JavaScript
            count = params.get("count", 5)
            script = f"""
            () => {{
                const comments = [];
                const commentElements = document.querySelectorAll('ytd-comment-thread-renderer');
                for (let i = 0; i < Math.min(commentElements.length, {count}); i++) {{
                    const el = commentElements[i];
                    const authorEl = el.querySelector('#author-text span');
                    const textEl = el.querySelector('#content-text');
                    if (textEl) {{
                        comments.push({{
                            author: authorEl ? authorEl.innerText.trim() : 'Anônimo',
                            text: textEl.innerText.trim()
                        }});
                    }}
                }}
                return comments;
            }}
            """
            result = page.evaluate(script)
            return {"success": True, "comments": result, "count": len(result)}

        elif action == "eval":
            script = params.get("script", "")
            result = page.evaluate(script)
            return {"success": True, "result": str(result)[:5000]}

        elif action == "status":
            return {
                "success": True,
                "title": page.title() if page else None,
                "url": page.url if page else None,
                "browser_open": browser is not None
            }

        elif action == "close":
            if browser:
                browser.close()
                playwright.stop()
            return {"success": True, "message": "Browser closed"}

        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


class BrowserHandler(BaseHTTPRequestHandler):
    """Handler HTTP para receber comandos"""

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            cmd = json.loads(post_data.decode('utf-8'))
            result = execute_command(cmd)
        except Exception as e:
            result = {"success": False, "error": str(e)}

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_GET(self):
        # Status check
        result = execute_command({"action": "status"})
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, format, *args):
        print(f"[Browser Server] {args[0]}")


def main():
    # Inicializa browser na startup
    init_browser()

    # Inicia servidor HTTP
    server = HTTPServer(('0.0.0.0', 8888), BrowserHandler)
    print("Browser Server rodando em http://0.0.0.0:8888")
    print("Comandos: POST com JSON {action: 'goto', params: {url: '...'}}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
        print("\nServer encerrado")


if __name__ == "__main__":
    main()
