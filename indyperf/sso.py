import requests

CLIENT_CREDENTIALS_GRANT_TYPE = 'client_credentials'
PASSWORD_GRANT_TYPE = 'password'

DEFAULT_SSO_GRANT_TYPE = CLIENT_CREDENTIALS_GRANT_TYPE

SSO_ENABLE='enabled'
SSO_GRANT_TYPE = 'grant-type'
SSO_URL = 'url'
SSO_REALM = 'realm'
SSO_CLIENT_ID = 'client-id'
SSO_CLIENT_SECRET = 'client-secret'
SSO_USERNAME = 'username'
SSO_PASSWORD = 'password'

def get_sso_token(suite):
    if suite.sso is None or suite.sso.get(SSO_ENABLE) is False:
        return None

    grant_type = suite.sso.get(SSO_GRANT_TYPE) or DEFAULT_SSO_GRANT_TYPE

    if grant_type == DEFAULT_SSO_GRANT_TYPE:
        form = {
            'grant_type': grant_type, 
            'client_id': suite.sso[SSO_CLIENT_ID],
            'client_secret': suite.sso[SSO_CLIENT_SECRET]
        }
    elif grant_type == PASSWORD_GRANT_TYPE:
        form = {
            'grant_type': grant_type, 
            'client_id': suite.sso[SSO_CLIENT_ID],
            'username': suite.sso[SSO_USERNAME],
            'password': suite.sso[SSO_PASSWORD]
        }


    url = f"{suite.sso[SSO_URL]}/auth/realms/{suite.sso[SSO_REALM]}/protocol/openid-connect/token"

    response = requests.post(url, data=form, verify=suite.ssl_verify)
    response.raise_for_status()

    token = response.json()['access_token']
    suite.set_sso_token(token)

    return token
