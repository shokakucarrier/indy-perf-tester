import requests
import os
import json
from shutil import rmtree
from datetime import datetime as dt
from urllib.parse import urlparse
from indyperf.utils import (run_cmd, POST_HEADERS)

LOCAL_REPO = "/tmp/local-repo-%(id)s"

PROXY_SETTINGS = """
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
"""

DEPLOY_SETTINGS = """
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
"""

SETTINGS = """
<?xml version="1.0"?>
<settings>
  <localRepository>%(local_repo)s</localRepository>
  <interactiveMode>false</interactiveMode>

  <mirrors>
    <mirror>
      <id>indy</id>
      <mirrorOf>*</mirrorOf>
      <url>%(mirror_url)s</url>
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

  %(proxy_settings)s

  %(deploy_settings)s
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

def clean_local_repo(id):
    rmtree(LOCAL_REPO % {'id': id})

def cleanup_build_group(id, suite):
    """Remove the group created specifically to channel content into this build,
       since we're done with it now.
    """

    print(f"Deleting temporary group:{id} used for build time only")
    resp = requests.delete(f"{suite.env.indy_url}/api/admin/group/{id}", headers=suite.headers, verify=suite.env.ssl_verify)
    resp.raise_for_status()


def create_repos_and_settings(builddir, id, suite):
    """
    Create the necessary hosted repos and groups, then generate a Maven settings.xml file 
    to work with them.
    """

    if suite.env.do_promote is True:
        create_missing_stores(id, suite)

    parsed = urlparse(suite.env.indy_url)

    params = {
        'url':suite.env.indy_url, 
        'id': id, 
        'local_repo': LOCAL_REPO % {'id': id},
        'host': parsed.hostname, 
        'port': parsed.port, 
        'proxy_enabled': str(suite.env.proxy_enabled).lower(),
        'proxy_port': suite.env.proxy_port,
        'token': suite.token,
        'headers': "\n".join([f"<property><name>{name}</name><value>{value}</value></property>" for name,value in suite.headers.items()])
    }

    mirror_url = "%(url)s/api/folo/track/%(id)s/maven/group/%(id)s" % params
    if suite.env.do_promote is False:
        mirror_url = "%(url)s/api/content/%(target)s" % {'url': params['url'], 'target': suite.env.mirror_target.replace(':', '/')}

    print(f"Mirror URL is: {mirror_url}")
    params['mirror_url'] = mirror_url


    proxy_settings = ""
    if suite.env.proxy_enabled is True:
        proxy_settings = PROXY_SETTINGS % params

    params['proxy_settings'] = proxy_settings

    deploy_settings = ""
    if 'deploy' in suite.env.mvn_goals:
        deploy_settings = DEPLOY_SETTINGS % params

    params['deploy_settings'] = deploy_settings


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
            suite.promotion_target,
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

        base_url = f"{suite.env.indy_url}/api/admin/stores/{package_type}/{store_type}"
        resp = requests.head(f"{base_url}/{store['name']}", headers=suite.headers, verify=suite.env.ssl_verify)
        if resp.status_code == 404:
            print("POSTing: %s" % json.dumps(store, indent=2))

            resp = requests.post(base_url, json=store, headers=post_headers, verify=suite.env.ssl_verify)
            resp.raise_for_status()


