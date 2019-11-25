import requests
import os
import json
from datetime import datetime as dt
from urllib.parse import urlparse
from indyperf.utils import (run_cmd, POST_HEADERS)

SETTINGS = """
<?xml version="1.0"?>
<settings>
  <localRepository>/tmp/repository</localRepository>
  <interactiveMode>false</interactiveMode>

  <mirrors>
    <mirror>
      <id>indy</id>
      <mirrorOf>*</mirrorOf>
      <url>%(url)s/api/folo/track/%(id)s/maven/group/%(id)s</url>
    </mirror>
  </mirrors>

  <servers>
    <server>
      <id>indy</id>
      <configuration>
        <httpConfiguration>
          <all>
            <connectionTimeout>60000</connectionTimeout>
            <headers>
              %(headers)s
            </headers>
          </all>
        </httpConfiguration>
      </configuration>
    </server>
  </servers>

  <proxies>
    <proxy>
      <id>indy-httprox</id>
      <active>%(proxy_enabled)s</active>
      <protocol>http</protocol>
      <host>%(host)s</host>
      <port>%(proxy_port)s</port>
      <username>%(id)s+tracking</username>
      <password>%(token)s</password>
      <nonProxyHosts>%(host)s</nonProxyHosts>
    </proxy>
  </proxies>

  <profiles>
    <profile>
      <id>deploy-settings</id>
      <properties>
        <altDeploymentRepository>indy::default::%(url)s/api/folo/track/%(id)s/maven/hosted/%(id)s</altDeploymentRepository>
      </properties>
    </profile>
  </profiles>

  <activeProfiles>
    <activeProfile>deploy-settings</activeProfile>
  </activeProfiles>
</settings>
"""

def setup_builddir(builds_dir, build, tid_base):
    """ Setup physical directory for executing the build, then checkout the sources there. """

    if os.path.isdir(builds_dir) is False:
        os.makedirs(builds_dir)

    builddir="%s/%s-%s" % (builds_dir, tid_base, dt.now().strftime("%Y%m%dT%H%M%S"))

    run_cmd("git clone -l -b %s %s %s" % (build.git_branch, build.git_url, builddir))
    
    builddir = os.path.join(os.getcwd(), builddir)
    tid = os.path.basename(builddir)

    return (builddir, tid)


def cleanup_build_group(id, suite):
    """Remove the group created specifically to channel content into this build,
       since we're done with it now.
    """

    print(f"Deleting temporary group:{id} used for build time only")
    resp = requests.delete(f"{suite.indy_url}/api/admin/group/{id}", headers=suite.headers, verify=suite.ssl_verify)
    resp.raise_for_status()


def create_repos_and_settings(builddir, id, suite):
    """
    Create the necessary hosted repos and groups, then generate a Maven settings.xml file 
    to work with them.
    """

    parsed = urlparse(suite.indy_url)
    proxy_enabled = 'true' if  is True else 'false'
    params = {
        'url':suite.indy_url, 
        'id': id, 
        'host': parsed.hostname, 
        'port': parsed.port, 
        'proxy_enabled': str(suite.proxy_enabled).lower(),
        'proxy_port': suite.proxy_port,
        'token': suite.token,
        'headers': "\n".join([f"<property><name>{name}</name><value>{value}</value></property>" for name,value in suite.headers.items()])
    }

    create_missing_stores(id, suite)

    # Write the settings.xml we need for this build
    with open("%s/settings.xml" % builddir, 'w') as f:
        f.write(SETTINGS % params)


def create_missing_stores(id, suite):
    suite.stores.append({
        'type': 'hosted', 
        'key': f"maven:hosted:{id}", 
        'disabled': False, 
        'doctype': 'hosted', 
        'name': id, 
        'allow_releases': True
    })

    suite.stores.append({
        'type': 'group', 
        'name': id, 
        'constituents': [
            f"maven:hosted:{id}", 
            'maven:group:builds',
            'maven:group:brew_proxies',
            'maven:hosted:shared-imports',
            'maven:group:public'
        ]
    })

    post_headers = {**POST_HEADERS, **suite.headers}
    print(f"Using POST headers for repo creation:\n\n{post_headers}")

    for store in suite.stores:
        store_type = store['type']
        package_type = store.get('package_type')
        if package_type is None:
            package_type = 'maven'
            store['package_type'] = package_type

        name = store['name']
        store['key'] = f"{package_type}:{store_type}:{name}"
        store['doctype'] = store_type
        store['disabled'] = False

        base_url = f"{suite.indy_url}/api/admin/stores/{package_type}/{store_type}"
        resp = requests.head(f"{base_url}/{store['name']}", headers=suite.headers, verify=suite.ssl_verify)
        if resp.status_code == 404:
            print("POSTing: %s" % json.dumps(store, indent=2))

            resp = requests.post(base_url, json=store, headers=post_headers, verify=suite.ssl_verify)
            resp.raise_for_status()


