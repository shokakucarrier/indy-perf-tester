import requests

def seal_folo_report(id, suite):
    """Seal the Folo tracking report after the build completes"""

    print(f"Sealing folo tracking report for: {id}")
    resp = requests.post(f"{suite.indy_url}/api/folo/admin/{id}/record", data={})
    resp.raise_for_status()


def pull_folo_report(id, suite):
    """Pull the Folo tracking report associated with the current build"""

    print(f"Retrieving folo tracking report for: {id}")
    resp = requests.get(f"{suite.indy_url}/api/folo/admin/{id}/record")
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

    print(f"Promoting dependencies from {len(to_promote.keys())} sources into hosted:shared-imports")
    for key in to_promote:
        req = {'source': key, 'target': 'hosted:shared-imports', 'paths': to_promote[key]}
        resp = requests.post(f"{suite.indy_url}/api/promotion/paths/promote", json=req, headers=POST_HEADERS)
        resp.raise_for_status()

def promote_output_by_path(id, suite):
    """Run by-path promotion of uploaded content"""

    print(f"Promoting build output in hosted:{id} to membership of hosted:builds")
    req = {'source': f"hosted:{id}", 'target': 'hosted:builds'}
    resp = requests.post(f"{suite.indy_url}/api/promotion/paths/promote", json=req, headers=POST_HEADERS)
    resp.raise_for_status()


def promote_output_by_group(id, suite):
    """Run by-group promotion of uploaded content"""

    print(f"Promoting build output in hosted:{id} to membership of group:builds")
    req = {'source': f"hosted:{id}", 'targetGroup': 'builds'}
    resp = requests.post(f"{suite.indy_url}/api/promotion/groups/promote", json=req, headers=POST_HEADERS)
    resp.raise_for_status()


