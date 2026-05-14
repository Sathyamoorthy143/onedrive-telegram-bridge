from app.models.events import CommandRequest, NormalizedEvent

VALID_COMMANDS = {'start', 'list', 'search', 'get', 'help', 'sync', 'status'}


def parse_command(event: NormalizedEvent) -> CommandRequest:
    text = (event.text or '').strip()
    if not text:
        return CommandRequest(name='help', args='', raw_text=text, event=event)

    # If it's a command starting with /
    if text.startswith('/'):
        text = text[1:]
        parts = text.split(maxsplit=1)
        name = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ''

        if name not in VALID_COMMANDS:
            return CommandRequest(name='help', args='', raw_text=event.text, event=event)

        return CommandRequest(name=name, args=args, raw_text=event.text, event=event)

    # If it's just normal chat text, pass it through as a chat command for mirroring
    return CommandRequest(name='chat', args=text, raw_text=event.text, event=event)