from __future__ import annotations

from app.models.events import CommandRequest, CommandResponse


class CommandHandler:
    def __init__(self, onedrive_service, state_store):
        self.onedrive = onedrive_service
        self.store = state_store

    def handle(self, request: CommandRequest) -> CommandResponse:
        match request.name:
            case 'start':
                return self._start(request)
            case 'list':
                return self._list(request)
            case 'search':
                return self._search(request)
            case 'get':
                return self._get(request)
            case 'sync':
                return self._sync_status(request)
            case 'status':
                return self._status(request)
            case 'chat':
                return self._chat(request)
            case _:
                return self._help(request)

    def _list(self, request: CommandRequest) -> CommandResponse:
        path_arg = request.args or None
        current_path = None

        # If arg is a number, resolve it to a cached folder path
        if path_arg and path_arg.strip().isdigit():
            cached = self.store.get_cached_item(
                request.event.channel, request.event.chat_id, path_arg.strip()
            )
            if cached:
                # Use the item's path as the new listing target
                current_path = cached.get('item_path', '').lstrip('/')
                path_arg = current_path
            else:
                return CommandResponse(
                    ok=False,
                    message=f'No item #{path_arg} found. Run /list first.'
                )
        else:
            current_path = path_arg or '/'

        try:
            items = self.onedrive.list_files(path=path_arg)
        except RuntimeError as e:
            return CommandResponse(ok=False, message=str(e), should_mirror=False)
        except Exception as e:
            return CommandResponse(ok=False, message=f'OneDrive error: {e}', should_mirror=False)

        self.store.cache_result_items(
            request.event.channel, request.event.chat_id,
            request.event.correlation_id, items
        )
        msg = self._format_items(current_path, items)
        return CommandResponse(ok=True, message=msg, data={'items': items})

    def _search(self, request: CommandRequest) -> CommandResponse:
        if not request.args:
            return CommandResponse(ok=False, message='Usage: search <keyword>')
        try:
            items = self.onedrive.search_files(request.args)
        except RuntimeError as e:
            return CommandResponse(ok=False, message=str(e))
        except Exception as e:
            return CommandResponse(ok=False, message=f'OneDrive error: {e}')
        self.store.cache_result_items(request.event.channel, request.event.chat_id, request.event.correlation_id, items)
        msg = self._format_items(f"Search results for: {request.args}", items)
        return CommandResponse(ok=True, message=msg, data={'items': items})

    def _get(self, request: CommandRequest) -> CommandResponse:
        if not request.args:
            return CommandResponse(ok=False, message='Usage: get <index-or-file-id>')
        try:
            cached = self.store.get_cached_item(request.event.channel, request.event.chat_id, request.args)
            item_id = cached['item_id'] if cached else request.args
            meta = self.onedrive.get_file_metadata(item_id)
            url = self.onedrive.get_download_url(item_id)
        except RuntimeError as e:
            return CommandResponse(ok=False, message=str(e))
        except Exception as e:
            return CommandResponse(ok=False, message=f'OneDrive error: {e}')
        message = (
            f"Ready: {meta['name']}\n"
            f"Type: {meta['type']}\n"
            f"Path: {meta['path']}\n"
            f"Download: {url}"
        )
        return CommandResponse(ok=True, message=message, data={'file': meta, 'download_url': url})

    def _sync_status(self, request: CommandRequest) -> CommandResponse:
        return CommandResponse(ok=True, message='Sync service disabled (Telegram only mode).')

    def _status(self, request: CommandRequest) -> CommandResponse:
        try:
            # Check OneDrive connectivity
            drive_items = self.onedrive.list_files(top=1)
            od_status = "✅ Connected"
        except Exception as e:
            od_status = f"❌ Error: {str(e)[:50]}"

        lines = [
            "🛡️ *Bridge Status*",
            f"• OneDrive: {od_status}",
            f"• Telegram: ✅ Active",
            "",
            f"Environment: {request.event.metadata.get('mode', 'production')}",
        ]
        return CommandResponse(ok=True, message='\n'.join(lines))

    def _start(self, request: CommandRequest) -> CommandResponse:
        message = (
            f'👋 Welcome to OneDrive Command Bridge!\n\n'
            f'I can help you access your OneDrive files via Telegram.\n\n'
            f'📂 Available commands:\n'
            f'• /list [path] — list files\n'
            f'• /search <keyword> — search files\n'
            f'• Just type a <number> to open/download it\n'
            f'• /sync — check sync status\n'
            f'• /help — show help\n\n'
            f'Try /list to see your OneDrive files!'
        )
        return CommandResponse(ok=True, message=message)

    def _chat(self, request: CommandRequest) -> CommandResponse:
        text = request.args.strip()
        
        # If it's a number, try to intelligently auto-navigate
        if text.isdigit():
            cached = self.store.get_cached_item(request.event.channel, request.event.chat_id, text)
            if cached:
                if cached.get('item_type') == 'folder':
                    # Pretend it was a /list command
                    request.name = 'list'
                    return self._list(request)
                else:
                    # Pretend it was a /get command
                    request.name = 'get'
                    return self._get(request)
                    
        # A normal text message (not starting with /)
        return CommandResponse(ok=True, message="")

    def _help(self, request: CommandRequest) -> CommandResponse:
        message = (
            '📂 *Available Commands*\n'
            '• /list [path] — List files/folders\n'
            '• /search <keyword> — Search files\n'
            '• /get <index> — Get file download link\n'
            '• /status — Check bridge health\n'
            '• /help — Show this message\n\n'
            '💡 *Tip:* You can just type a number from the list to open it!'
        )
        return CommandResponse(ok=True, message=message)

    @staticmethod
    def _format_items(current_path: str, items: list[dict]) -> str:
        path_label = current_path.strip('/') or 'OneDrive (root)'
        if not items:
            return f'📂 {path_label}\n\nFolder is empty.'

        lines = [f'📂 {path_label}', '']
        folders = [i for i in items if i['type'] == 'folder']
        files   = [i for i in items if i['type'] != 'folder']

        for idx, item in enumerate(items, start=1):
            icon = '📁' if item['type'] == 'folder' else '📄'
            lines.append(f'{idx}. {icon} {item["name"]}')

        lines.append('')
        if folders:
            lines.append('Open a folder: just type its <number>')
        if files:
            lines.append('Get a file link: just type its <number>')
        lines.append('Search files: /search <keyword>')
        return '\n'.join(lines)