import click
import os
import indyperf.updown as updown
import indyperf.build as build
import indyperf.config as config

@click.command()
@click.argument('suite_yml')
@click.argument('builder_idx')
@click.argument('total_builders')
@click.option('-E', '--env-yml', 
    type=click.Path(exists=True), default='/target/env.yml', 
    help='Target environment, including Indy/DA URLs and Indy proxy port')
def run(suite_yml, builder_idx, total_builders, env_yml):
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
    suite = config.read_config(env_yml, suite_yml)
    order = config.create_build_order(suite, builder_idx, total_builders)

    for build in order.iter():
        print(f"Running build: {build.name}")

        tid_base = f"build_{build.name}"

        builddir = setup_builddir(os.getcwd(), build, tid_base)
        tid = os.path.basename(builddir)

        create_repos_and_settings(builddir, tid, suite);

        do_pme(builddir, build)
        do_build(builddir, build)

        seal_folo_report(tid, suite)

        folo_report = pull_folo_report(tid, suite)
        promote_deps_by_path(folo_report, tid, suite)

        if promote_by_path is True:
            promote_output_by_path(tid, suite)
        else:
            promote_output_by_group(tid, suite)

        cleanup_build_group(tid, suite)
