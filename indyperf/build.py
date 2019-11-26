import os
from indyperf.updown import (setup_builddir, create_repos_and_settings, cleanup_build_group)
from indyperf.promote import (seal_folo_report, pull_folo_report, promote_deps_by_path, promote_output_by_path, promote_output_by_group)
from indyperf.utils import run_cmd

DEFAULT_PME_ARGS = [
    "-DrestURL={da_url}",
    "-DversionIncrementalSuffix={pme_version_suffix}",
    "-DallowConfigFilePrecedence=true",
    "-DrepoReportingRemoval=true",
    "-DdependencySource=REST",
    "-DrepoRemovalBackup=repositories-backup.xml",
    "-DprojectSrcSkip=false",
    "-DversionIncrementalSuffixPadding=5",
    "-DversionSuffixStrip="
]

def do_pme(builddir, build, suite):
    ctx_dir = build.git_context_dir or '.'

    print(f"Raw PME args: '{build.pme_args}'")
    args = build.pme_args or " ".join(DEFAULT_PME_ARGS)
    args = args.format(da_url=suite.da_url, pme_version_suffix=suite.pme_version_suffix)

    ret = run_cmd(f"java -jar /usr/share/pme/pme.jar -f {ctx_dir}/pom.xml -s ./settings.xml {args} 2>&1 | tee ./pme.log", builddir, fail=False)
    print(f"PME return code is {ret}")
    if ret == 0:
        return True
    else:
        return False


def do_build(builddir, build, suite):
    ctx_dir = build.git_context_dir or '.'

    print(f"Raw maven args: '{build.mvn_args}'")
    args = build.mvn_args or ''
    args = args.format(indy_url=suite.indy_url)

    ret = run_cmd(f"mvn -f {ctx_dir}/pom.xml -s ./settings.xml {args} clean deploy 2>&1 | tee ./mvn.log", builddir, fail=False)
    print(f"Maven return code is {ret}")
    if ret == 0:
        return True
    else:
        return False


