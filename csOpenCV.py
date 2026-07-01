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
from csorchestrator.frontend.step.step_github_action import StepAddGitHubAction
from csorchestrator.frontend.step.step_custom_command import (
    StepBashScriptCommand,
    StepInstallAptPackages,
    StepWinPSCommand,
)
from csorchestrator.frontend.step.step_get_precompiled_lib_github import (
    StepGetPrecompiledLibGithub,
)

from csorchestrator.frontend.local_execution.step_utils import (
    StepExecuteOnlyOn,
    StepExecuteOnlyOncePerMatrix,
    StepSkipExecutionOnLocal,
)

from csorchestrator.application.factory.factory import (
    OptionalOrchestratorWithReport,
    create_orchestrator_factory_all_supported_cases,
)
from csorchestrator.application.cli.cli import orchestrator_main_with_default_run
from csorchestrator.domain.context.context_os_architecture import OS, UBUNTU_VERSIONS
from csorchestrator.domain.context.context_os_architecture import UBUNTU_STRING_PREFIX


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
        name="csOpenCV",
        version="0.1.0",
        execution_matrix_name="orchestrator-matrix",
        use_ninjamulti=False,
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
    p = o.create_phase("Install Requirements (Linux-Ubuntu)")

    p.add_step(
        StepBashScriptCommand(
            name="set non interactive installer",
            description="install apt packages if not already installed in the system",
            cmd=[
                "# Pre-accept the Microsoft Core Fonts EULA so installation can run non-interactively.",
                "sudo apt update",
                'echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | sudo debconf-set-selections',
                "sudo DEBIAN_FRONTEND=noninteractive apt install -y ttf-mscorefonts-installer",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="remove libunwind (Ubuntu 22.04)",
            description="remove libunwind",
            cmd=[
                "# Remove libunwind causing errors on ubuntu 22.04",
                "sudo apt remove libunwind-*",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.LINUX, version_starts_with=UBUNTU_VERSIONS.UBUNTU_22_04.value
            )
        )
    )

    p.add_step(
        StepInstallAptPackages(
            name="install apt packages",
            description="install apt packages if not already installed in the system",
            packages=[
                "gstreamer1.0*",
                "libavcodec-dev",
                "libavformat-dev",
                "libdc1394-dev",
                "libgstreamer-plugins-base1.0-dev",
                "libgstreamer1.0-dev",
                "libgtk-3-dev",
                "libjpeg-dev",
                "libopenexr-dev",
                "libpng-dev",
                "libswscale-dev",
                "libtbb-dev",
                "libtbb12",
                "libtiff-dev",
                "libwebp-dev",
                "pkg-config",
                "python3-dev",
                "python3-numpy",
                "python3-pip",
                "ubuntu-restricted-extras",
            ],
            dry_run=False,
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepAddGitHubAction(
            name="Cache Cuda installer",
            description="cache cuda installer",
            id="cuda_cache",
            uses="actions/cache@v6",
            with_list=[
                "path: ${{ runner.temp }}/cuda_13.3.1_windows.exe",
                "key: cuda-installer-13.3.1",
            ],
        ).add_extra(StepExecuteOnlyOn(os=OS.WINDOWS))
    )

    p.add_step(
        StepWinPSCommand(
            name="Install CUDA (Windows 10)",
            description="install cuda",
            # from https://developer.nvidia.com/cuda-downloads?target_os=Windows&target_arch=x86_64&target_version=10&target_type=exe_local
            cmd=[
                '$ErrorActionPreference = "Stop"',
                "",
                'if ("${{ steps.cuda_cache.outputs.cache-hit }}" -eq "true") {',
                '    Write-Host "CUDA installer cache HIT"',
                "} else {",
                '    Write-Host "CUDA installer cache MISS"',
                "}",
                "",
                '$installer = "$env:TEMP\cuda_13.3.1_windows.exe"',
                "",
                "if (Test-Path $installer) {",
                '    Write-Host "Installer present on disk"',
                "}",
                "",
                "if (-not (Test-Path $installer)) {",
                '  Write-Host "Download CUDA installer..."',
                "  $download = [System.Diagnostics.Stopwatch]::StartNew()",
                '  $url = "https://developer.download.nvidia.com/compute/cuda/13.3.1/local_installers/cuda_13.3.1_windows.exe"',
                "  Invoke-WebRequest -Uri $url -OutFile $installer",
                "  $download.Stop()",
                '  Write-Host ("Download took {0:mm\:ss}" -f $download.Elapsed)',
                "}",
                "else {",
                '  Write-Host "Using existing CUDA installer: $installer"',
                "}",
                "",
                "$install = [System.Diagnostics.Stopwatch]::StartNew()",
                '$p = Start-Process -FilePath $installer -ArgumentList "-s" -Wait -PassThru',
                "$install.Stop()",
                'Write-Host ("Installation took {0:mm\:ss}" -f $install.Elapsed)',
                "",
                "if ($p.ExitCode -ne 0) {",
                '    throw "Installer failed with exit code $($p.ExitCode)"',
                "}",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.WINDOWS))
    )

    p.add_step(
        StepWinPSCommand(
            name="Verify CUDA (Windows 10)",
            description="verify cuda installation",
            cmd=[
                '$nvcc = "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v13.3\\bin\\nvcc.exe"',
                "",
                "if (!(Test-Path $nvcc)) {",
                '  throw "nvcc not found: $nvcc"',
                "}",
                "",
                "& $nvcc --version",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.WINDOWS))
    )

    p.add_step(
        StepAddGitHubAction(
            name="Cache cuDNN installer",
            description="cache cuDNN installer",
            id="cudnn_cache",
            uses="actions/cache@v6",
            with_list=[
                "path: ${{ runner.temp }}/cudnn_9.23.2_windows_x86_64.exe",
                "key: cudnn-installer-9.23.2",
            ],
        ).add_extra(StepExecuteOnlyOn(os=OS.WINDOWS))
    )

    p.add_step(
        StepWinPSCommand(
            name="Install cuDNN (Windows 10)",
            description="install cuDNN",
            # from https://developer.nvidia.com/cudnn-downloads?target_os=Windows&target_arch=x86_64&target_version=10&target_type=exe_local
            cmd=[
                '$ErrorActionPreference = "Stop"',
                "",
                'if ("${{ steps.cudnn_cache.outputs.cache-hit }}" -eq "true") {',
                '    Write-Host "cuDNN installer cache HIT"',
                "} else {",
                '    Write-Host "cuDNN installer cache MISS"',
                "}",
                "",
                '$installer = "$env:TEMP\cudnn_9.23.2_windows_x86_64.exe"',
                "",
                "if (Test-Path $installer) {",
                '    Write-Host "Installer present on disk"',
                "}",
                "",
                "if (-not (Test-Path $installer)) {",
                '  Write-Host "Downloading cuDNN installer..."',
                "  $download = [System.Diagnostics.Stopwatch]::StartNew()",
                '  $url = "https://developer.download.nvidia.com/compute/cudnn/9.23.2/local_installers/cudnn_9.23.2_windows_x86_64.exe"',
                "  Invoke-WebRequest -Uri $url -OutFile $installer",
                "  $download.Stop()",
                '  Write-Host ("Download took {0:mm\:ss}" -f $download.Elapsed)',
                "}",
                "else {",
                '  Write-Host "Using existing cuDNN installer: $installer"',
                "}",
                "",
                "$install = [System.Diagnostics.Stopwatch]::StartNew()",
                '$p = Start-Process -FilePath $installer -ArgumentList "-s" -Wait -PassThru',
                "$install.Stop()",
                'Write-Host ("Installation took {0:mm\:ss}" -f $install.Elapsed)',
                "",
                "if ($p.ExitCode -ne 0) {",
                '    throw "Installer failed with exit code $($p.ExitCode)"',
                "}",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.WINDOWS))
    )

    p.add_step(
        StepWinPSCommand(
            name="Verify cuDNN (Windows 10)",
            description="verify cuDNN installation",
            cmd=[
                '$dll = Get-ChildItem -Path "C:\\Program Files\\NVIDIA" -Recurse -Filter "cudnn*.dll" -ErrorAction SilentlyContinue',
                "if (-not $dll) {",
                '  throw "cuDNN DLL not found."',
                "}",
                "",
                'Write-Host "Found cuDNN:"',
                "$dll | Select-Object FullName",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(StepExecuteOnlyOn(os=OS.WINDOWS))
    )

    p.add_step(
        StepBashScriptCommand(
            name="Install CUDA (Ubuntu 24.04)",
            description="install cuda",
            cmd=[
                "wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-ubuntu2404.pin",
                "sudo mv cuda-ubuntu2404.pin /etc/apt/preferences.d/cuda-repository-pin-600",
                "wget -q https://developer.download.nvidia.com/compute/cuda/13.3.1/local_installers/cuda-repo-ubuntu2404-13-3-local_13.3.1-610.43.02-1_amd64.deb",
                "sudo dpkg -i cuda-repo-ubuntu2404-13-3-local_13.3.1-610.43.02-1_amd64.deb",
                "sudo cp /var/cuda-repo-ubuntu2404-13-3-local/cuda-*-keyring.gpg /usr/share/keyrings/",
                "sudo apt update",
                "sudo apt install -y cuda-toolkit-13-3",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.LINUX, version_starts_with=UBUNTU_VERSIONS.UBUNTU_24_04.value
            )
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="Install CUDA (Ubuntu 22.04)",
            description="install cuda",
            cmd=[
                "wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin",
                "sudo mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600",
                "wget -q https://developer.download.nvidia.com/compute/cuda/13.3.1/local_installers/cuda-repo-ubuntu2204-13-3-local_13.3.1-610.43.02-1_amd64.deb",
                "sudo dpkg -i cuda-repo-ubuntu2204-13-3-local_13.3.1-610.43.02-1_amd64.deb",
                "sudo cp /var/cuda-repo-ubuntu2204-13-3-local/cuda-*-keyring.gpg /usr/share/keyrings/",
                "sudo apt update",
                "sudo apt install -y cuda-toolkit-13-3",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(
                os=OS.LINUX, version_starts_with=UBUNTU_VERSIONS.UBUNTU_22_04.value
            )
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="Install cudnn (Ubuntu)",
            description="install cudnn",
            cmd=[
                "wget -q https://developer.download.nvidia.com/compute/cudnn/9.23.2/local_installers/cudnn-local-repo-debian12-9.23.2_1.0-1_amd64.deb",
                "sudo dpkg -i cudnn-local-repo-debian12-9.23.2_1.0-1_amd64.deb",
                "sudo cp /var/cudnn-local-repo-debian12-9.23.2/cudnn-*-keyring.gpg /usr/share/keyrings/",
                "sudo apt update",
                "sudo apt -y install libcudnn9-cuda-13 libcudnn9-dev-cuda-13",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
        )
    )

    p.add_step(
        StepBashScriptCommand(
            name="verify a cuda stub library exists",
            description="verify cuda stub library exists",
            cmd=[
                "ls /usr/local/cuda/lib64/stubs/libcuda.so",
            ],
        )
        .add_extra(StepExecuteOnlyOncePerMatrix())
        .add_extra(
            StepExecuteOnlyOn(os=OS.LINUX, version_starts_with=UBUNTU_STRING_PREFIX)
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
