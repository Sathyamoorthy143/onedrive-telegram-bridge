from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import msal
import requests

from app.config import settings, ROOT_DIR

logger = logging.getLogger(__name__)

_CACHE_FILE  = ROOT_DIR / 'data' / 'msal_cache.json'
_AUTHORITY   = 'https://login.microsoftonline.com/common'
_SCOPES      = ['Files.ReadWrite', 'User.Read']
_GRAPH_ROOT  = 'https://graph.microsoft.com/v1.0'


class OneDriveService:
    """Delegated-auth OneDrive client using a persisted MSAL token cache.

    Call ``setup_auth.py`` once to populate ``data/msal_cache.json``.
    After that, tokens auto-refresh indefinitely.
    """

    def __init__(self):
        self._cache = msal.SerializableTokenCache()
        self._app: msal.PublicClientApplication | None = None
        self._load_cache()

    # ── cache helpers ────────────────────────────────────────────────────────

    def _load_cache(self):
        if _CACHE_FILE.exists():
            self._cache.deserialize(_CACHE_FILE.read_text(encoding='utf-8'))

    def _save_cache(self):
        if self._cache.has_state_changed:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(self._cache.serialize(), encoding='utf-8')

    # ── MSAL app ─────────────────────────────────────────────────────────────

    def _get_app(self) -> msal.PublicClientApplication:
        if self._app is None:
            self._app = msal.PublicClientApplication(
                client_id=settings.microsoft_client_id,
                authority=_AUTHORITY,
                token_cache=self._cache,
            )
        return self._app

    def _token(self) -> str:
        app = self._get_app()
        accounts = app.get_accounts()
        result = None

        if accounts:
            result = app.acquire_token_silent(_SCOPES, account=accounts[0])

        if not result or 'access_token' not in result:
            raise RuntimeError(
                'OneDrive is not authorized. '
                'Run:  .venv\\Scripts\\python.exe setup_auth.py'
            )

        self._save_cache()
        return result['access_token']

    def _headers(self) -> Dict[str, str]:
        return {'Authorization': f'Bearer {self._token()}'}

    # ── drive root URL ───────────────────────────────────────────────────────

    def _base_drive_url(self) -> str:
        """Always use /me/drive with delegated auth."""
        return f'{_GRAPH_ROOT}/me/drive'

    # ── public API ───────────────────────────────────────────────────────────

    def list_files(self, path: Optional[str] = None, top: Optional[int] = None) -> List[Dict]:
        clean = (path or settings.onedrive_root_path or '').strip('/')
        if clean:
            url = f'{self._base_drive_url()}/root:/{clean}:/children'
        else:
            url = f'{self._base_drive_url()}/root/children'
        resp = requests.get(
            url, headers=self._headers(),
            params={'$top': top or settings.max_results}, timeout=30
        )
        resp.raise_for_status()
        return [self._normalize_item(x) for x in resp.json().get('value', [])]

    def search_files(self, keyword: str, top: Optional[int] = None) -> List[Dict]:
        url = f"{self._base_drive_url()}/root/search(q='{keyword}')"
        resp = requests.get(
            url, headers=self._headers(),
            params={'$top': top or settings.max_results}, timeout=30
        )
        resp.raise_for_status()
        return [self._normalize_item(x) for x in resp.json().get('value', [])]

    def get_file_metadata(self, item_id: str) -> Dict:
        url = f'{self._base_drive_url()}/items/{item_id}'
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return self._normalize_item(resp.json())

    def get_download_url(self, item_id: str) -> str:
        url = f'{self._base_drive_url()}/items/{item_id}'
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get('@microsoft.graph.downloadUrl', '')

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_item(item: Dict) -> Dict:
        parent = item.get('parentReference', {})
        path = parent.get('path', '').replace('/drive/root:', '')
        return {
            'id':      item.get('id', ''),
            'name':    item.get('name', ''),
            'path':    f"{path}/{item.get('name', '')}".replace('//', '/'),
            'type':    'folder' if 'folder' in item else 'file',
            'size':    item.get('size', 0),
            'web_url': item.get('webUrl', ''),
        }