import msal, os, json, requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path('.env'))

tenant_id = os.getenv('MICROSOFT_TENANT_ID')
client_id = os.getenv('MICROSOFT_CLIENT_ID')
client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
user_id = os.getenv('ONEDRIVE_USER_ID')

app = msal.ConfidentialClientApplication(
    client_id=client_id,
    client_credential=client_secret,
    authority=f'https://login.microsoftonline.com/{tenant_id}',
)
result = app.acquire_token_for_client(scopes=['https://graph.microsoft.com/.default'])

if 'access_token' not in result:
    print('Auth FAILED:', result.get('error_description', result))
else:
    token = result['access_token']
    print('Auth OK')

    endpoints = [
        f'https://graph.microsoft.com/v1.0/users/{user_id}/drive/root/children',
        f'https://graph.microsoft.com/v1.0/users/{user_id}/drive',
        f'https://graph.microsoft.com/v1.0/users/{user_id}',
    ]

    headers = {'Authorization': f'Bearer {token}'}
    for url in endpoints:
        resp = requests.get(url, headers=headers, params={'$top': 5}, timeout=15)
        print(f'\nURL: {url}')
        print(f'Status: {resp.status_code}')
        try:
            body = resp.json()
            if 'error' in body:
                print(f'Error code: {body["error"]["code"]}')
                print(f'Error msg:  {body["error"]["message"]}')
            else:
                keys = list(body.keys())
                print(f'Response keys: {keys}')
                if 'value' in body:
                    print(f'Items count: {len(body["value"])}')
                    for item in body['value'][:3]:
                        print(f'  - {item.get("name")} [{item.get("folder","") and "folder" or "file"}]')
        except Exception as e:
            print(f'Parse error: {e}')
