import requests

def get_sso_token(suite):
    if suite.sso.enabled is False:
        return None

    response = requests.post(suite.sso.url, data=suite.sso.form, verify=suite.env.ssl_verify)
    response.raise_for_status()

    token = response.json()['access_token']
    suite.set_sso_token(token)

    return token
