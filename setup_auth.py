"""
setup_auth.py - One-time OneDrive authorization.

Opens your browser, you log in, tokens are saved permanently.
Uses http://localhost:6060 as the redirect URI (must be registered in Azure).

Usage:
    .\.venv\Scripts\python.exe setup_auth.py
"""
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

from dotenv import load_dotenv
import msal
import requests as req

ROOT_DIR     = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / '.env')

CACHE_FILE   = ROOT_DIR / 'data' / 'msal_cache.json'
CLIENT_ID    = os.getenv('MICROSOFT_CLIENT_ID', '')
AUTHORITY    = 'https://login.microsoftonline.com/common'
SCOPES       = ['Files.ReadWrite', 'User.Read']
REDIRECT_URI = 'http://localhost:6060'
PORT         = 6060

_auth_code  = None
_auth_error = None
_server_ref = None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Catches the OAuth2 redirect from Microsoft."""

    def do_GET(self):
        global _auth_code, _auth_error
        params = parse_qs(urlparse(self.path).query)

        if 'code' in params:
            _auth_code = params['code'][0]
            body = b'<h2>Authorization successful! Return to your terminal.</h2>'
        elif 'error' in params:
            desc = params.get('error_description', [params.get('error', ['Unknown'])[0]])[0]
            _auth_error = desc
            body = f'<h2>Error: {desc}</h2>'.encode()
        else:
            body = b'<h2>Waiting...</h2>'

        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

        # Shut down after receiving the callback
        threading.Thread(target=_server_ref.shutdown, daemon=True).start()

    def log_message(self, fmt, *args):
        pass  # silence HTTP logs


def main():
    global _auth_code, _auth_error, _server_ref

    if not CLIENT_ID:
        print('ERROR: MICROSOFT_CLIENT_ID is not set in .env')
        sys.exit(1)

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cache = msal.SerializableTokenCache()
    if CACHE_FILE.exists():
        cache.deserialize(CACHE_FILE.read_text(encoding='utf-8'))

    app = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )

    # Try silent refresh first (if already logged in before)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and 'access_token' in result:
            print(f'Already authorized as: {accounts[0]["username"]}')
            _save_and_verify(result, cache)
            return

    # Build the login URL
    auth_url = app.get_authorization_request_url(SCOPES, redirect_uri=REDIRECT_URI)

    # Start local callback server
    _server_ref = HTTPServer(('localhost', PORT), _CallbackHandler)

    print()
    print('--- OneDrive Authorization ---')
    print('Opening your browser...')
    print(f'If it does not open, visit:\n  {auth_url}\n')
    webbrowser.open(auth_url)
    print(f'Waiting for login (server on localhost:{PORT})...')

    _server_ref.serve_forever()  # blocks until callback received

    if _auth_error:
        print(f'\nAuthorization failed: {_auth_error}')
        sys.exit(1)

    if not _auth_code:
        print('\nNo authorization code received.')
        sys.exit(1)

    # Exchange code for tokens
    result = app.acquire_token_by_authorization_code(
        _auth_code,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    if 'access_token' in result:
        _save_and_verify(result, cache)
    else:
        print('\nToken exchange failed:')
        print(result.get('error_description', result.get('error', str(result))))
        sys.exit(1)


def _save_and_verify(result: dict, cache: msal.SerializableTokenCache):
    CACHE_FILE.write_text(cache.serialize(), encoding='utf-8')
    print(f'\nTokens saved to: {CACHE_FILE}')

    headers = {'Authorization': f'Bearer {result["access_token"]}'}
    r = req.get('https://graph.microsoft.com/v1.0/me/drive', headers=headers, timeout=10)
    if r.status_code == 200:
        data = r.json()
        quota    = data.get('quota', {})
        used_gb  = round(quota.get('used', 0) / 1e9, 2)
        total_gb = round(quota.get('total', 0) / 1e9, 2)
        print(f'OneDrive connected!')
        print(f'  Drive: {data.get("name", "My Drive")}')
        print(f'  Owner: {data.get("owner", {}).get("user", {}).get("displayName", "")}')
        print(f'  Space: {used_gb} GB / {total_gb} GB')
        print()
        print('You can now start the bot:  .\\restart.ps1')
    else:
        print(f'Drive check returned {r.status_code}: {r.text[:300]}')
        print('Tokens saved anyway.')


if __name__ == '__main__':
    main()
