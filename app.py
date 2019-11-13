#!/usr/bin/env python

import os
import sys
import time
import requests
import json

from ruamel.yaml import YAML
from datetime import datetime as dt
# from urlparse import urlparse
from urllib.parse import urlparse

ENVAR_SUITE_YML = 'SUITE_YML'
ENVAR_BUILDERS = 'BUILDERS'
ENVAR_INDY_URL = 'INDY_URL'
ENVAR_PROXY_PORT = 'PROXY_PORT'

SUITE_CATALOG_DIR = os.environ.get('SUITE_CATALOG_DIR') or '/suites'

TEST_BUILDS_SECTION = 'builds'
TEST_PROMOTE_BY_PATH_FLAG = 'promote-by-path'
TEST_STORES = 'stores'

BUILD_MVN_ARGS = 'mvn-args'
BUILD_PME_ARGS = 'pme-args'
BUILD_GIT_URL = 'git-url'
BUILD_GIT_BRANCH = 'git-branch'
BUILD_GIT_CONTEXT_DIR = 'git-context-dir'
BUILD_TIMES = 'times'


DEFAULT_STORES = [
    {          
        'type': 'hosted', 
        'name': 'builds', 
        'allow_releases': True
    },
    {
        'type': 'hosted', 
        'name': 'shared-imports', 
        'allow_releases': True
    },
    {
        'type': 'group', 
        'name': 'builds', 
        'constituents': [
            "maven:hosted:builds"
        ]
    },
    {
        'type': 'group', 
        'name': 'brew_proxies'
    }
]

SETTINGS = """
<?xml version="1.0"?>
<settings>
  <localRepository>/tmp/repository</localRepository>
  <mirrors>
    <mirror>
      <id>indy</id>
      <mirrorOf>*</mirrorOf>
      <url>%(url)s/api/folo/track/%(id)s/maven/group/%(id)s</url>
    </mirror>
  </mirrors>
  <proxies>
    <proxy>
      <id>indy-httprox</id>
      <active>true</active>
      <protocol>http</protocol>
      <host>%(host)s</host>
      <port>%(proxy_port)s</port>
      <username>%(id)s+tracking</username>
      <password>foo</password>
      <nonProxyHosts>%(host)s</nonProxyHosts>
    </proxy>
  </proxies>
  <profiles>
    <profile>
      <id>resolve-settings</id>
      <repositories>
        <repository>
          <id>central</id>
          <url>%(url)s/api/folo/track/%(id)s/maven/group/%(id)s</url>
          <releases>
            <enabled>true</enabled>
          </releases>
          <snapshots>
            <enabled>false</enabled>
          </snapshots>
        </repository>
      </repositories>
      <pluginRepositories>
        <pluginRepository>
          <id>central</id>
          <url>%(url)s/api/folo/track/%(id)s/maven/group/%(id)s</url>
          <releases>
            <enabled>true</enabled>
          </releases>
          <snapshots>
            <enabled>false</enabled>
          </snapshots>
        </pluginRepository>
      </pluginRepositories>
    </profile>
    
    <profile>
      <id>deploy-settings</id>
      <properties>
        <altDeploymentRepository>%(id)s::default::%(url)s/api/folo/track/%(id)s/maven/hosted/%(id)s</altDeploymentRepository>
      </properties>
    </profile>
    
  </profiles>
  <activeProfiles>
    <activeProfile>resolve-settings</activeProfile>
    
    <activeProfile>deploy-settings</activeProfile>
    
  </activeProfiles>
</settings>
"""

POST_HEADERS = {'content-type': 'application/json', 'accept': 'application/json'}


def run_build():
    """ 
    Main entry point. Read envars, calculate the ordered build list for this builder, and execute each build in the ordered list.

    NOTE: Builds that match this builder's index will be run in an interleaved method, where a build that is to run 5 times does
    not run that single build all 5 times before proceeding to the next matching build. Instead, each matching build will be run,
    then the build array will be processed again with a pass counter to see what matching builds have a build-count that exceeds
    the current pass counter. This will proceed until the pass counter exceeds the build-count for all matching builds.
    """

    # try:
    (suite_config, builders, builder_idx, indy_url, proxy_port) = read_env()

    promote_by_path = suite_config.get(TEST_PROMOTE_BY_PATH_FLAG) or True
    stores = suite_config.get(TEST_STORES) or DEFAULT_STORES
    builds = suite_config.get(TEST_BUILDS_SECTION) or {}

    ordered_builds = create_build_order(builds, builders, builder_idx)

    for build_name in ordered_builds:
        run_build(build_name, builds, promote_by_path, stores, indy_url, proxy_port)

def read_env():
    """ Read the suite configuration that this worker should run, from envars. 

    Once we have a suite YAML file (from the SUITE_YML envar), that file will be parsed
    and passed back with the rest of the envar values.

    If any required envars are missing and don't have default values, error messages will
    be generated. If the list of errors is non-empty at the end of this method, an error
    message containing all of the problems will be logged to the console.
    """

    suite_yml = os.environ.get(ENVAR_SUITE_YML)
    indy_url = os.environ.get(ENVAR_INDY_URL)
    proxy_port = os.environ.get(ENVAR_PROXY_PORT) or '8081'
    builders = os.environ.get(ENVAR_BUILDERS)
    nodename = os.environ.get(ENVAR_NODENAME)

    errors = []
    if indy_url is None:
        errors.append(f"Missing Indy URL envar: {ENVAR_INDY_URL}")

    if builders is None:
        errors.append(f"Missing builder count envar: {ENVAR_BUILDERS}")

    if suite_yml is None:
        errors.append(f"Missing test suite configfile envar: {ENVAR_SUITE_YML}")
    elif os.path.exists(os.path.join( SUITE_CATALOG_DIR, suite_yml )):
        suite_file = os.path.join( SUITE_CATALOG_DIR, suite_yml )
        with open( suite_file ) as f:
            yaml = YAML(typ='safe')
            suite_config = yaml.load(f)
    else:
        errors.append( f"Missing suite config file: {os.path.join(SUITE_CATALOG_DIR, suite_yml)}")

    if nodename is None:
        errors.append(f"Missing nodename envar: {ENVAR_NODENAME}")
    else:
        builder_idx = int(nodename.split('-')[-1])

    if len(errors) > 0:
        print("\n".join(errors))
        raise Exception("Invalid configuration")

    return (suite_config, builders, builder_idx, indy_url, proxy_port)


def create_build_order(builds, builders, builder_idx):
    """ Iterate through the builds in this suite configuration, finding all builds that match the current builder index.

    Builds are matched using a synthetic array index (the order given in the build map will be used to generate a synthetic array index here).

    Matching builds will satisfy (synthetic_index % builder-count == builder-index).

    Once a build matches, its name is added to a list of includes, and if its build-count number exceeds the maximum seen, it will be used as
    the maximum-build-passes number.

    Then, the include list will be processed once for each pass in the build-passes number. If the pass-index is less than included build's 
    build-count (defaulting to 1), then the build's name is included (again) in the ordered-builds array. This will build up an interleaved
    build script to be executed here.
    """
    included_builds = []

    counter=0
    passes = 0
    for name,build in builds.items():
        if counter % builders == builder_idx:
            included_builds.append(name)
            build_passes = build.get(BUILD_TIMES) or 1
            if build_passes > passes:
                passes = build_passes

    ordered_builds = []
    for passidx in range(passes):
        for name in included_builds:
            build = builds[name]
            build_passes = build.get(BUILD_TIMES) or 1
            if passidx < build_passes:
                ordered_builds.append(name)

    print(f"My build order:\n{"\n- ".join(ordered_builds)}")

    return ordered_builds


def run_build(build_name, builds, promote_by_path, stores, indy_url, proxy_port):
    """ Execute the named build.

        Build steps include:
        
            * Setup all relevant repositories and groups in Indy
            * Checkout project source code
            * Execute PME against DA URL (TODO)
            * Setup a Maven settings.xml for the build
            * Execute Maven with the given settings.xml
            * Pull the resulting tracking record
            * Promote dependencies
            * Promote build output
            * Cleanup relevant repos / groups from Indy

        NOTE: This process should mimic the calls and sequence executed by PNC as closely as possible!
    """
    print(f"Running build: {build_name}")
    return

    tid_base = f"build_{build_name}"

    project_src_dirname = build.get(BUILD_SOURCE_DIR) or build_name
    project_src_dir = os.path.join( src_basedir, project_src_dirname)

    git_branch = build.get(BUILD_GIT_BRANCH) or 'master'
    builddir = setup_builddir(os.getcwd(), project_src_dir, git_branch, tid_base)

    tid = os.path.basename(builddir)
    parsed = urlparse(indy_url)
    params = {
        'url':indy_url, 
        'id': tid, 
        'host': parsed.hostname, 
        'port': parsed.port, 
        'proxy_port': proxy_port
    }

    create_repos_and_settings(builddir, stores, params);

    do_pme(builddir)
    do_build(builddir)
    seal_folo_report(params)

    folo_report = pull_folo_report(params)
    promote_deps_by_path(folo_report, params)

    if promote_by_path is True:
        promote_output_by_path(params)
    else:
        promote_output_by_group(params)

    cleanup_build_group(params)

    # except (KeyboardInterrupt,SystemExit,Exception) as e:
    #     print(e)


def setup_builddir(builds_dir, projectdir, branch, tid_base):
    """ Setup physical directory for executing the build, then checkout the sources there. """

    if os.path.isdir(builds_dir) is False:
        os.makedirs(builds_dir)

    builddir="%s/%s-%s" % (builds_dir, tid_base, dt.now().strftime("%Y%m%dT%H%M%S"))

    run_cmd("git clone -l -b %s file://%s %s" % (branch, projectdir, builddir))
    
    return os.path.join(os.getcwd(), builddir)


def run_cmd(cmd, fail=True):
    """Run the specified command. If fail == True, and a non-zero exit value 
       is returned from the process, raise an exception
    """
    print(cmd)
    ret = os.system(cmd)
    if ret != 0:
        print("Error running command: %s (return value: %s)" % (cmd, ret))
        if fail:
            raise Exception("Failed to run: '%s' (return value: %s)" % (cmd, ret))


def create_repos_and_settings(builddir, stores, params):
    """
    Create the necessary hosted repos and groups, then generate a Maven settings.xml file 
    to work with them.
    """

    create_missing_stores(stores, params)

    # Write the settings.xml we need for this build
    with open("%s/settings.xml" % builddir, 'w') as f:
        f.write(SETTINGS % params)


def create_missing_stores(stores, params):
    stores.append({
        'type': 'hosted', 
        'key': f"maven:hosted:{params['id']}", 
        'disabled': False, 
        'doctype': 'hosted', 
        'name': params['id'], 
        'allow_releases': True
    })

    stores.append({
        'type': 'group', 
        'name': params['id'], 
        'constituents': [
            f"maven:hosted:{params['id']}", 
            'maven:group:builds',
            'maven:group:brew_proxies',
            'maven:hosted:shared-imports',
            'maven:group:public'
        ]
    })

    for store in stores:
        store_type = store['type']
        package_type = store.get('package_type')
        if package_type is None:
            package_type = 'maven'
            store['package_type'] = package_type

        name = store['name']
        store['key'] = f"{package_type}:{store_type}:{name}"
        store['doctype'] = store_type
        store['disabled'] = False

        base_url = f"{params['url']}/api/admin/stores/{package_type}/{store_type}"
        resp = requests.head(f"{base_url}/{store['name']}")
        if resp.status_code == 404:
            print("POSTing: %s" % json.dumps(store, indent=2))

            resp = requests.post(base_url, json=store, headers=POST_HEADERS)
            resp.raise_for_status()


def do_pme(builddir):
    """ TODO: Run PME, which should talk to DA and pull metadata files from the Indy instance. """


def do_build(builddir):
    run_cmd("mvn -f %(d)s/pom.xml -s %(d)s/settings.xml clean deploy 2>&1 | tee %(d)s/build.log" % {'d': builddir}, fail=False)


def seal_folo_report(params):
    """Seal the Folo tracking report after the build completes"""

    print("Sealing folo tracking report for: %(id)s" % params)
    resp = requests.post("%(url)s/api/folo/admin/%(id)s/record" % params, data={})
    resp.raise_for_status()


def pull_folo_report(params):
    """Pull the Folo tracking report associated with the current build"""

    print("Retrieving folo tracking report for: %(id)s" % params)
    resp = requests.get("%(url)s/api/folo/admin/%(id)s/record" % params)
    resp.raise_for_status()

    return resp.json()


def promote_deps_by_path(folo_report, params):
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

    print("Promoting dependencies from %s sources into hosted:shared-imports" % len(to_promote.keys()))
    for key in to_promote:
        req = {'source': key, 'target': 'hosted:shared-imports', 'paths': to_promote[key]}
        resp = requests.post("%(url)s/api/promotion/paths/promote" % params, json=req, headers=POST_HEADERS)
        resp.raise_for_status()

def promote_output_by_path(params):
    """Run by-path promotion of uploaded content"""

    print("Promoting build output in hosted:%(id)s to membership of hosted:builds" % params)
    req = {'source': 'hosted:%(id)s' % params, 'target': 'hosted:builds'}
    resp = requests.post("%(url)s/api/promotion/paths/promote" % params, json=req, headers=POST_HEADERS)
    resp.raise_for_status()


def promote_output_by_group(params):
    """Run by-group promotion of uploaded content"""

    print("Promoting build output in hosted:%(id)s to membership of group:builds" % params)
    req = {'source': 'hosted:%(id)s' % params, 'targetGroup': 'builds'}
    resp = requests.post("%(url)s/api/promotion/groups/promote" % params, json=req, headers=POST_HEADERS)
    resp.raise_for_status()


def cleanup_build_group(params):
    """Remove the group created specifically to channel content into this build,
       since we're done with it now.
    """

    print("Deleting temporary group:%(id)s used for build time only" % params)
    resp = requests.delete("%(url)s/api/admin/group/%(id)s" % params)
    resp.raise_for_status()


if __name__ == "__main__":
    try:
        run_build()
    finally:
        print("Finished. Sleeping...")
        while True:
            time.sleep(1)
