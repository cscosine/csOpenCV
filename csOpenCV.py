#!/usr/bin/env python3
import sys
from pathlib import Path
from typing import Sequence

from csorchestrator.foundation.core.report import Report
from csorchestrator.foundation.core.optional_result_with_report import (
    OptionalResultWithReport,
)
from csorchestrator.foundation.git.resolve_url import RepoUrlParts

from csorchestrator.domain.orchestrator.workflow_config import (
    WorkflowConfig,
    Cron,
    DayOfWeek,
    ReleaseCreationOnTagConfig,
)

from csorchestrator.frontend.cscmake_presets.supported_variants import (
    BuildConfig,
)

from csorchestrator.frontend.step.step_get_repository import (
    StepGetRepositoryGitHub,
    StepGetRepositoryExtraDepthOne,
    StepGetRepositoryExtraAccessToken,
)
from csorchestrator.frontend.step.step_cmake_command import StepCMakeWorkflow
from csorchestrator.frontend.step.step_get_versions_from_cmake_config_package_version import (
    StepGetVersionsFromCMakeConfigPackageVersion,
    CMakeConfigPackageVersion,
)
from csorchestrator.frontend.step.step_create_archives import StepCreateArchives
from csorchestrator.frontend.step.step_upload_artifacts import (
    StepUploadArtifacts,
    create_artifact_prefix_from_orchestrator_name_version,
)
from csorchestrator.frontend.step.step_get_precompiled_lib_github import (
    StepGetPrecompiledLibGithub,
)

from csorchestrator.frontend.local_execution.step_utils import (
    StepExecuteOnlyOncePerMatrix,
    StepSkipExecutionOnLocal,
)

from csorchestrator.application.factory.factory import (
    OptionalOrchestratorWithReport,
    create_orchestrator_factory_all_supported_cases,
)
from csorchestrator.application.cli.cli import orchestrator_main_with_default_run


def create_orchestrator() -> OptionalOrchestratorWithReport:
    report = Report()

    base_target_dir = Path("workspace")
    base_install_dir = base_target_dir / Path("install")
    base_libs_dir = base_target_dir / Path("libs")
    common_repo_ref = "dev"

    opencv_version = "5.0.0"

    repos: dict[str, None | BuildConfig] = {
        "csCMake": None,
        "opencv": BuildConfig.DEBUG_RELEASE,
        "opencv_contrib": None,
    }

    o = create_orchestrator_factory_all_supported_cases(
        name="csOpenCV", version="0.1.0", execution_matrix_name="orchestrator-matrix"
    )

    o.wf_config = WorkflowConfig(
        on_push_branches=["main", "dev"],
        on_push_tags=["'v*.*.*'"],
        on_pull_request_branches=["main"],
        on_dispatch=True,
        on_schedule=Cron.weekly(DayOfWeek.MON, hour=3),
        create_release_on_tag=ReleaseCreationOnTagConfig(name="release-from-artifacts"),
    )

    # ----------------------------------------------------------------
    p = o.create_phase("Repos Update")
    for repo in repos.keys():
        p.add_step(
            StepGetRepositoryGitHub(
                name=f"{repo} Git clone/pull-ff",
                description=f"Clone or pull-ff {repo} description",
                target_directory=(base_target_dir / repo).as_posix(),
                repo_url_parts=RepoUrlParts(
                    repo_base_url=StepGetRepositoryGitHub.GITHUB_BASE_URL_SSH,
                    repo_org="cscosine",
                    repo_name=repo + ".git",
                ),
                repo_ref=common_repo_ref,
            )
            .add_extra(
                StepGetRepositoryExtraDepthOne(
                    on_local_checkout=False,
                    on_github_action_checkout=True,
                )
            )
            .add_extra(StepExecuteOnlyOncePerMatrix())
            .add_extra(
                StepGetRepositoryExtraAccessToken("${{ secrets.ACTIONS_ORG_ACCESS }}")
            )
        )

    # ----------------------------------------------------------------
    p = o.create_phase("Get Precompiled Libraries")

    list_3rdPartyBaseLibs: dict[str, str] = {
        "eigen3": "3.4.0",
    }

    for lib_name, lib_version in list_3rdPartyBaseLibs.items():
        p.add_step(
            StepGetPrecompiledLibGithub(
                name=f"Get Precompiled Lib {lib_name} from 3rdPartyBaseLibs",
                description="get precompiled lib from github release",
                base_url=StepGetPrecompiledLibGithub.GITHUB_BASE_URL_HTTPS,
                org="cscosine",
                project_name="3rdPartyBaseLibs",
                project_tag="v0.1.0-test",
                lib_name=lib_name,
                lib_version=lib_version,
                base_libs_dir=base_libs_dir,
            )
        )

    # ----------------------------------------------------------------
    p = o.create_phase("Configure-Build-Test-Install")
    for repo, config in repos.items():
        if config is not None:
            p.add_step(
                StepCMakeWorkflow(
                    name=f"{repo} CMake Workflow",
                    description=f"CMake workflow for {repo} with config: {config}",
                    source_dir=(base_target_dir / repo).as_posix(),
                    config=config,
                )
            )

    # ----------------------------------------------------------------
    p = o.create_phase("Create and Upload Artifacts")
    p.add_step(
        StepGetVersionsFromCMakeConfigPackageVersion(
            name="Get Versions",
            description="Get Versions for all libs",
            repos_version=[CMakeConfigPackageVersion("opencv", opencv_version)],
            base_install_dir=base_install_dir,
            id="versions",
            output_dict_name="packages",
        )
    )

    p.add_step(
        StepCreateArchives(
            name="Create Archives",
            description="Create archives with libs and versions",
            input_id="versions",
            input_dict="packages",
            base_install_dir=base_install_dir,
        ).add_extra(StepSkipExecutionOnLocal())
    )

    p.add_step(
        StepUploadArtifacts(
            name="Upload Artifacts",
            description="Upload Artifacts with libs and versions",
            base_install_dir=base_install_dir,
            artifact_prefix=create_artifact_prefix_from_orchestrator_name_version(o),
        )
    )

    return OptionalResultWithReport.createResultAndReport(o, report)


def main(argv: Sequence[str] | None = None) -> int:
    script_path = str(Path(__file__).resolve())
    return orchestrator_main_with_default_run(script_path, argv)


if __name__ == "__main__":
    sys.exit(main())
