import requests
from indyperf.utils import POST_HEADERS

def seal_folo_report(id, suite):
    """Seal the Folo tracking report after the build completes"""

    post_headers = {**POST_HEADERS, **suite.headers}
    print(f"Sealing folo tracking report for: {id}")
    resp = requests.post(f"{suite.indy_url}/api/folo/admin/{id}/record", data={}, headers=post_headers, verify=suite.ssl_verify)
    resp.raise_for_status()


def pull_folo_report(id, suite):
    """Pull the Folo tracking report associated with the current build"""

    post_headers = {**POST_HEADERS, **suite.headers}
    print(f"Retrieving folo tracking report for: {id}")
    resp = requests.get(f"{suite.indy_url}/api/folo/admin/{id}/record", headers=post_headers, verify=suite.ssl_verify)
    resp.raise_for_status()

    return resp.json()


def promote_deps_by_path(folo_report, id, suite):
    """Run by-path promotion of downloaded content"""
    to_promote = {}

    downloads = folo_report.get('downloads')
    if downloads is not None:
        for download in downloads:
            key = download['storeKey']
            mode = download['accessChannel']
            if mode == 'MAVEN_REPO' and key.startswith('remote:'):
                path = download['path']

                paths = to_promote.get(key)
                if paths is None:
                    paths = []
                    to_promote[key]=paths

                    paths.append(path)

    post_headers = {**POST_HEADERS, **suite.headers}
    print(f"Promoting dependencies from {len(to_promote.keys())} sources into hosted:shared-imports")

    target = 'maven:hosted:shared-imports'

    success = True
    for key in to_promote:
        req = {'source': key, 'target': target, 'paths': to_promote[key]}
        resp = requests.post(f"{suite.indy_url}/api/promotion/paths/promote", json=req, headers=post_headers, verify=suite.ssl_verify)
        resp.raise_for_status()

        success = check_promote_status( resp, key, target )

    return success

def check_promote_status( resp, key, target ):
    print(f"Promotion result:\n\n{resp.text}")
    err = resp.json().get('error')
    if err is not None and len(err) > 0:
        print(f"Failed to promote from: {key} to: {target}. Error: {err}")
        return False
    else:
        print(f"Promotion of {key} to {target} succeeded.")

    return True

def promote_output_by_path(id, suite):
    """Run by-path promotion of uploaded content"""

    key = f"maven:hosted:{id}"
    target = 'maven:hosted:builds'

    post_headers = {**POST_HEADERS, **suite.headers}
    print(f"Promoting build output in hosted:{id} to membership of hosted:builds")
    req = {'source': key, 'target': target}
    resp = requests.post(f"{suite.indy_url}/api/promotion/paths/promote", json=req, headers=post_headers, verify=suite.ssl_verify)
    resp.raise_for_status()

    return check_promote_status( resp, key, target )

def promote_output_by_group(id, suite):
    """Run by-group promotion of uploaded content"""

    key = f"maven:hosted:{id}"
    target = 'builds'

    post_headers = {**POST_HEADERS, **suite.headers}
    print(f"Promoting build output in hosted:{id} to membership of group:builds")
    req = {'source': key, 'targetGroup': target}
    resp = requests.post(f"{suite.indy_url}/api/promotion/groups/promote", json=req, headers=post_headers, verify=suite.ssl_verify)
    resp.raise_for_status()

    return check_promote_status( resp, key, target )

