import click
import os
import sys
from time import sleep
from traceback import format_exc
import indyperf.updown as updown
import indyperf.build as builds
import indyperf.promote as promote
import indyperf.config as config
import indyperf.sso as sso

@click.command()
@click.argument('env_yml') #, help='Target environment, including Indy/DA URLs and Indy proxy port')
@click.argument('suite_yml') #, help='Test suite configuration')
@click.argument('builder_idx') #, help='The zero-based index of this builder')
@click.argument('total_builders') #, help='The total number of builders in this test')
@click.option('-B', '--builds-dir', help='Base directory where builds should be cloned and run (defaults to $PWD)')
def run(env_yml, suite_yml, builder_idx, total_builders, builds_dir):
    """ Execute a test run from start to end.

        This will read a YAML file containing variables for the target environment, and
        another YAML file containing the suite of builds to run. Using each build's specified
        number of rebuilds, along with the total number of concurrent builder clients and this
        client's builder index, it will then construct an ordered list of builds to execute.

        When it has the ordered list of builds, it iterates through, building each one in turn.
        The order of builds will likely contain duplicates if any builds are specified to run 
        more than once. Otherwise, builds should be in the order specified in the suite YAML. 

        Steps for each build include:
        
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
    suite = config.read_config(suite_yml, env_yml)
    order = config.create_build_order(suite, builder_idx, total_builders)
    if builds_dir is None:
        builds_dir = os.getcwd()

    print(f"SSL verification enabled? {suite.env.ssl_verify}")
    sso.get_sso_token(suite)

    build_results = {}
    fails = 0
    for build in order.iter():
        print(f"Running build: {build.name}")
        result = build_results.get(build.name, [0,0])

        tid_base = f"build_perftest-{build.name}"

        try:
            (builddir, tid) = updown.setup_builddir(builds_dir, build, tid_base)

            updown.create_repos_and_settings(builddir, tid, suite);

            print(f"Running test with:\n\nDA URL: {suite.env.da_url}\nIndy URL: {suite.env.indy_url}")

            success = True

            if suite.env.da_url is not None:
                success = builds.do_pme(builddir, build, suite)

            if success is True:
                success = builds.do_build(builddir, build, suite)

            if suite.env.do_promote is True:
                if success is True:
                    promote.seal_folo_report(tid, suite)

                    folo_report = promote.pull_folo_report(tid, suite)
                    success = promote.promote_deps_by_path(folo_report, tid, suite)

                if success is True:
                    if suite.promote_by_path is True:
                        success = promote.promote_output_by_path(tid, suite)
                    else:
                        success = promote.promote_output_by_group(tid, suite)

            if success is True:
                result[0]+=1
            else:
                result[1]+=1
                fails+=1

        except Exception as e:
            print(f"Build: {build.name} had an error:\n\n{format_exc()}\n\n")
            result[1]+=1
        finally:
            build_results[build.name] = result

            try:
                updown.clean_local_repo(tid)
                
                if suite.env.do_promote is True:
                    updown.cleanup_build_group(tid, suite)
            except Exception as cleanError:
                print(f"Build cleanup failed: {cleanError}")

        print(f"Pausing {suite.pause} before next build")
        sleep(suite.pause)

    result_headers = ['Successes', 'Failures']
    row_format = "{:>15}" * (len(result_headers) + 1)
    print(row_format.format("", *result_headers))
    for name,results in build_results.items():
        print(row_format.format(name, *results))

    if fails > 0:
        sys.exit(1)
