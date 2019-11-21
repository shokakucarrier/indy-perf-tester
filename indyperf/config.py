from ruamel.yaml import YAML
import os

ENV_INDY_URL = 'indy_url'
ENV_DA_URL = 'DA_url'
ENV_PROXY_PORT = 'proxy_port'

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

class Build:
    def __init__(self, name, spec):
        self.name = name
        self.mvn_args = spec.get(BUILD_MVN_ARGS)
        self.pme_args = spec.get(BUILD_PME_ARGS)
        self.git_url = spec.get(BUILD_GIT_URL)
        self.git_branch = spec.get(BUILD_GIT_BRANCH) or 'master'
        self.git_context_dir = spec.get(BUILD_GIT_CONTEXT_DIR)
        self.build_count = spec.get(BUILD_TIMES)

class Suite:
    def __init__(self, suite_spec, indy_url, da_url, proxy_port):
        self.suite_spec = suite_spec
        self.indy_url = indy_url
        self.da_url = da_url
        self.proxy_port = proxy_port

        self.promote_by_path = suite_spec.get(TEST_PROMOTE_BY_PATH_FLAG) or True
        self.stores = suite_spec.get(TEST_STORES) or DEFAULT_STORES.copy()

        build_specs = suite_spec.get(TEST_BUILDS_SECTION) or {}

        self.builds = {}
        for (name,spec) in build_specs.items():
            self.builds[name] = Build(name, spec)


class BuildOrder:
    def __init__(self, builds, ordered_build_names):
        self.builds = builds
        self.ordered_build_names = ordered_build_names

    def iter(self):
        return iter([builds[name] for name in self.ordered_build_names])


def read_config(env_yml, suite_yml):
    """ Read the suite configuration that this worker should run, from a config.yml file 
    (specified on the command line and passed in as a parameter here). 

    Once we have a suite YAML file (from the suite_yml config), that file will be parsed
    and passed back with the rest of the config values, in a Config object.

    If any required configs are missing and don't have default values, error messages will
    be generated. If the list of errors is non-empty at the end of this method, an error
    message containing all of the problems will be logged to the console and an
    exception will be raised.
    """
    if env_yml is None:
        errors.append(f"Missing test environment config file")
    elif os.path.exists(env_yml):
        with open(env_yml) as f:
            yaml = YAML(typ='safe')
            env = yaml.load(f)
    else:
        errors.append( f"Missing test environment config file")

    if suite_yml is None:
        errors.append(f"Missing test suite file")
    elif os.path.exists(suite_yml):
        with open(suite_yml) as f:
            yaml = YAML(typ='safe')
            suite_spec = yaml.load(f)
    else:
        errors.append( f"Missing test suite file")

    indy_url = env.get(ENV_INDY_URL)
    da_url = env.get(ENV_DA_URL)
    proxy_port = env.get(ENV_PROXY_PORT) or '8081'

    errors = []
    if indy_url is None:
        errors.append(f"Missing Indy URL configuration: {ENV_INDY_URL}")

    if builders is None:
        errors.append(f"Missing builder count configuration: {ENV_BUILDERS}")

    if builder_idx is None:
        errors.append(f"Missing builder configuration: {ENV_NODENAME}")

    if len(errors) > 0:
        print("\n".join(errors))
        raise Exception("Invalid configuration")

    return Suite(suite_spec, indy_url, da_url, proxy_port)


def create_build_order(config, builder_idx, total_builders):
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
    for build in config.builds.items():
        if counter % total_builders == builder_idx:
            included_builds.append(build.name)
            build_passes = build.build_count or 1
            if build_passes > passes:
                passes = build_passes

    ordered_builds = []
    for passidx in range(passes):
        for name in included_builds:
            build = config.builds[name]
            build_passes = build.build_count or 1
            if passidx < build_passes:
                ordered_builds.append(name)

    order_str = "\n- ".join(ordered_builds)
    print(f"My build order:\n{order_str}")

    return BuildOrder(builds, ordered_builds)


