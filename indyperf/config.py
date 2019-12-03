from ruamel.yaml import YAML
import os

ENV_INDY_URL = 'indy-url'
ENV_DA_URL = 'DA-url'
ENV_PROXY_ENABLED = 'proxy-enabled'
ENV_PROXY_PORT = 'proxy-port'
ENV_SSL_VERIFY = 'ssl-verify'
ENV_PME_VERSION_SUFFIX = 'pme-version-suffix'
ENV_SSO_SECTION = 'sso'
ENV_MVN_GOALS = 'mvn-goals'
ENV_DO_PROMOTE = 'do-promote'
ENV_MIRROR_TARGET = 'mirror-target'
ENV_PROMOTION_TARGET = 'promotion-target'

SSO_ENABLE='enabled'
SSO_GRANT_TYPE = 'grant-type'
SSO_URL = 'url'
SSO_REALM = 'realm'
SSO_CLIENT_ID = 'client-id'
SSO_CLIENT_SECRET = 'client-secret'
SSO_USERNAME = 'username'
SSO_PASSWORD = 'password'

TEST_BUILDS_SECTION = 'builds'
TEST_PROMOTE_BY_PATH_FLAG = 'promote-by-path'
TEST_STORES = 'stores'
TEST_PAUSE = 'pause-between-builds'

BUILD_MVN_ARGS = 'mvn-args'
BUILD_PME_ARGS = 'pme-args'
BUILD_GIT_URL = 'git-url'
BUILD_GIT_BRANCH = 'git-branch'
BUILD_GIT_CONTEXT_DIR = 'git-context-dir'
BUILD_TIMES = 'times'

CLIENT_CREDENTIALS_GRANT_TYPE = 'client_credentials'
PASSWORD_GRANT_TYPE = 'password'

DEFAULT_SSO_GRANT_TYPE = CLIENT_CREDENTIALS_GRANT_TYPE

DEFAULT_MIRROR_TARGET = 'maven:group:public'
DEFAULT_MVN_GOALS = 'deploy'
DEFAULT_PROMOTION_TARGET = 'maven:group:builds'
DEFAULT_PME_VERSION_SUFFIX='build'
DEFAULT_PAUSE = 5
DEFAULT_PROXY_ENABLED = False
DEFAULT_DO_PROMOTE = True
DEFAULT_PROXY_PORT = 8081
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

class Build:
    def __init__(self, name, spec):
        self.name = name
        self.mvn_args = spec.get(BUILD_MVN_ARGS)
        self.pme_args = spec.get(BUILD_PME_ARGS)
        self.git_url = spec.get(BUILD_GIT_URL)
        self.git_branch = spec.get(BUILD_GIT_BRANCH) or 'master'
        self.git_context_dir = spec.get(BUILD_GIT_CONTEXT_DIR)
        self.build_count = spec.get(BUILD_TIMES)

class Environment:
    def __init__(self, env_spec):
        self.indy_url = env_spec.get(ENV_INDY_URL)
        self.da_url = env_spec.get(ENV_DA_URL)
        self.proxy_enabled = env_spec.get(ENV_PROXY_ENABLED) or DEFAULT_PROXY_ENABLED
        self.proxy_port = env_spec.get(ENV_PROXY_PORT) or DEFAULT_PROXY_PORT
        self.pme_version_suffix = env_spec.get(ENV_PME_VERSION_SUFFIX) or DEFAULT_PME_VERSION_SUFFIX

        self.promotion_target = env_spec.get(ENV_PROMOTION_TARGET) or DEFAULT_PROMOTION_TARGET

        self.do_promote = env_spec.get(ENV_DO_PROMOTE)
        if self.do_promote is None:
            self.do_promote = DEFAULT_DO_PROMOTE

        if self.do_promote is False:
            self.mirror_target = env_spec.get(ENV_MIRROR_TARGET) or DEFAULT_MIRROR_TARGET

        self.ssl_verify = env_spec.get(ENV_SSL_VERIFY)
        if self.ssl_verify is None:
            self.ssl_verify = True

        self.mvn_goals = env_spec.get(ENV_MVN_GOALS) or DEFAULT_MVN_GOALS

class SingleSignOn:
    def __init__(self, sso_spec):
        if sso_spec is None or sso_spec.get(SSO_ENABLE) is False:
            self.enabled = False
        else:
            self.enabled = sso_spec[SSO_ENABLE]
            self.grant_type = sso_spec.get(SSO_GRANT_TYPE) or DEFAULT_SSO_GRANT_TYPE

            if self.grant_type == DEFAULT_SSO_GRANT_TYPE:
                self.form = {
                    'grant_type': self.grant_type, 
                    'client_id': sso_spec[SSO_CLIENT_ID],
                    'client_secret': sso_spec[SSO_CLIENT_SECRET]
                }

            elif self.grant_type == PASSWORD_GRANT_TYPE:
                self.form = {
                    'grant_type': self.grant_type, 
                    'client_id': sso_spec[SSO_CLIENT_ID],
                    'username': sso_spec[SSO_USERNAME],
                    'password': sso_spec[SSO_PASSWORD]
                }

            base_url = sso_spec[SSO_URL]
            if base_url.endswith('/'):
                base_url = base_url[:-1]

            self.url = f"{base_url}/auth/realms/{sso_spec[SSO_REALM]}/protocol/openid-connect/token"

class Suite:
    def __init__(self, suite_spec, env, sso):
        self.suite_spec = suite_spec
        self.env = env
        self.sso = sso

        self.headers = {}
        self.token = None

        self.promote_by_path = suite_spec.get(TEST_PROMOTE_BY_PATH_FLAG) or True
        self.pause = suite_spec.get(TEST_PAUSE) or DEFAULT_PAUSE
        self.stores = suite_spec.get(TEST_STORES) or DEFAULT_STORES.copy()

        build_specs = suite_spec.get(TEST_BUILDS_SECTION) or {}

        self.builds = {}
        for (name,spec) in build_specs.items():
            self.builds[name] = Build(name, spec)

    def set_sso_token(self, token):
        self.token = token
        self.headers = {
            'Authorization': f"Bearer {token}"
        }

class BuildOrder:
    def __init__(self, builds, ordered_build_names):
        self.builds = builds
        self.ordered_build_names = ordered_build_names

    def iter(self):
        return iter([self.builds[name] for name in self.ordered_build_names])


def read_config(suite_yml, env_yml):
    """ Read the suite configuration that this worker should run, from a config.yml file 
    (specified on the command line and passed in as a parameter here). 

    Once we have a suite YAML file (from the suite_yml config), that file will be parsed
    and passed back with the rest of the config values, in a Config object.

    If any required configs are missing and don't have default values, error messages will
    be generated. If the list of errors is non-empty at the end of this method, an error
    message containing all of the problems will be logged to the console and an
    exception will be raised.
    """
    errors = []

    env_spec = {}
    if env_yml is None:
        errors.append(f"Missing test environment config file")
    elif os.path.exists(env_yml):
        with open(env_yml) as f:
            yaml = YAML(typ='safe')
            env_spec = yaml.load(f)
    else:
        errors.append( f"Missing test environment config file")

    suite_spec = {}
    if suite_yml is None:
        errors.append(f"Missing test suite file")
    elif os.path.exists(suite_yml):
        with open(suite_yml) as f:
            yaml = YAML(typ='safe')
            suite_spec = yaml.load(f)
    else:
        errors.append( f"Missing test suite file")

    env = Environment(env_spec)

    errors = []
    if env.indy_url is None:
        errors.append(f"Missing Indy URL configuration: {ENV_INDY_URL}")

    # if env.da_url is None:
    #     errors.append(f"Missing DA URL configuration: {ENV_DA_URL}")

    if len(errors) > 0:
        print("\n".join(errors))
        raise Exception("Invalid configuration")

    if env.indy_url.endswith('/'):
        env.indy_url = env.indy_url[:-1]

    if env.da_url is not None and env.da_url.endswith('/'):
        env.da_url = env.da_url[:-1]

    return Suite(suite_spec, env, SingleSignOn(env_spec.get(ENV_SSO_SECTION)))


def create_build_order(suite, builder_idx, total_builders):
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
    for name, build in suite.builds.items():
        # print(f"Checking build: {name} ({counter} % {total_builders} == {builder_idx})")
        if counter % int(total_builders) == int(builder_idx):
            # print(f"Including build: {name}")
            included_builds.append(name)
            build_passes = build.build_count or 1
            if build_passes > passes:
                passes = build_passes
        counter+=1

    ordered_builds = []
    for passidx in range(passes):
        for name in included_builds:
            build = suite.builds[name]
            build_passes = build.build_count or 1
            if passidx < build_passes:
                ordered_builds.append(name)

    order_str = '- ' + "\n- ".join(ordered_builds)
    print(f"My build order:\n{order_str}")

    return BuildOrder(suite.builds, ordered_builds)


