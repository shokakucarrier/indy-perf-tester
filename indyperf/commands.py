import click
import os
from time import sleep
import indyperf.updown as updown
import indyperf.build as builds
import indyperf.promote as promote
import indyperf.config as config
import indyperf.sso as sso

@click.command()
@click.argument('suite_yml')
@click.argument('builder_idx')
@click.argument('total_builders')
@click.option('-E', '--env-yml', 
    type=click.Path(exists=True), default='/target/env.yml', 
    help='Target environment, including Indy/DA URLs and Indy proxy port')
@click.option('-S', '--sso-yml', 
    type=click.Path(exists=True), default='/target/sso.yml', 
    help='Target environment SSO configuration')
@click.option('-B', '--builds-dir', help='Base directory where builds should be cloned and run (defaults to $PWD)')
def run(suite_yml, builder_idx, total_builders, env_yml, sso_yml, builds_dir):
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
    suite = config.read_config(suite_yml, env_yml, sso_yml)
    order = config.create_build_order(suite, builder_idx, total_builders)
    if builds_dir is None:
        builds_dir = os.getcwd()

    sso.get_sso_token(suite)

    for build in order.iter():
        print(f"Running build: {build.name}")

        tid_base = f"build_perftest-{build.name}"

        try:
            (builddir, tid) = updown.setup_builddir(builds_dir, build, tid_base)

            updown.create_repos_and_settings(builddir, tid, suite);

            print(f"Running test with:\n\nDA URL: {suite.da_url}\nIndy URL: {suite.indy_url}")
            builds.do_pme(builddir, build, suite)
            builds.do_build(builddir, build, suite)

            promote.seal_folo_report(tid, suite)

            folo_report = promote.pull_folo_report(tid, suite)
            promote.promote_deps_by_path(folo_report, tid, suite)

            if suite.promote_by_path is True:
                promote.promote_output_by_path(tid, suite)
            else:
                promote.promote_output_by_group(tid, suite)
        except e as Exception:
            print(f"Build: {build.name} had an error: {e}")
        finally:
            updown.cleanup_build_group(tid, suite)

        print(f"Pausing {suite.pause} before next build")
        sleep(suite.pause)
