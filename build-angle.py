#!/usr/bin/env python3
"""Build portable ANGLE EGL and OpenGL ES runtime packages.

The packages contain ANGLE's public headers plus the shared EGL and GLESv2
libraries used by MystralNative's optional WebGL 2 implementation.

Supported platforms: Linux and macOS.
Source: https://chromium.googlesource.com/angle/angle
"""

import argparse
import os
import platform as host_platform
import shutil
import subprocess
import sys
from pathlib import Path

ANGLE_REPO = "https://chromium.googlesource.com/angle/angle"
ANGLE_REVISION = "107da744f62a319b3c6851694740d9ebf247d048"
DEPOT_TOOLS_REPO = (
    "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
)
DEPOT_TOOLS_REVISION = "f70835271105ca56d2cd5382a0118152bc2bdeea"


def git_revision(value):
    if len(value) != 40 or any(
        character not in "0123456789abcdefABCDEF" for character in value
    ):
        raise argparse.ArgumentTypeError(
            "revision must be a full 40-character Git commit"
        )
    return value.lower()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build ANGLE shared runtime libraries"
    )
    parser.add_argument("platform", choices=["linux", "mac"])
    parser.add_argument(
        "-archs", help="Target architectures (comma separated)", default="x64"
    )
    parser.add_argument("-config", choices=["Release", "Debug"], default="Release")
    parser.add_argument("-out", help="Output directory", default="build")
    parser.add_argument(
        "-revision",
        type=git_revision,
        help="ANGLE git revision",
        default=ANGLE_REVISION,
    )
    return parser.parse_args()


def run_command(command, cwd=None, env=None):
    print(f"Running: {' '.join(str(part) for part in command)}", flush=True)
    try:
        subprocess.check_call(command, cwd=cwd, env=env)
    except subprocess.CalledProcessError as error:
        print(f"Command failed with exit code {error.returncode}")
        sys.exit(error.returncode)


def require_host(target_platform):
    host = host_platform.system()
    expected = "Linux" if target_platform == "linux" else "Darwin"
    if host != expected:
        print(
            f"Error: {target_platform} ANGLE builds require a {expected} host "
            f"(current host: {host})"
        )
        sys.exit(1)


def ensure_git_checkout(directory, repository, revision):
    if not (directory / ".git").exists():
        if directory.exists():
            shutil.rmtree(directory)
        directory.parent.mkdir(parents=True, exist_ok=True)
        run_command(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                repository,
                str(directory),
            ]
        )

    run_command(["git", "fetch", "--depth", "1", "origin", revision], cwd=directory)
    run_command(["git", "checkout", "--force", "FETCH_HEAD"], cwd=directory)


def ensure_sources(root_dir, revision):
    third_party_dir = root_dir / "third_party"
    depot_tools_dir = third_party_dir / "depot_tools"
    source_dir = third_party_dir / "angle"

    ensure_git_checkout(depot_tools_dir, DEPOT_TOOLS_REPO, DEPOT_TOOLS_REVISION)
    ensure_git_checkout(source_dir, ANGLE_REPO, revision)

    gclient_config = """solutions = [
  {
    'name': '.',
    'url': 'https://chromium.googlesource.com/angle/angle',
    'managed': False,
    'custom_deps': {},
    'custom_vars': {
      'checkout_angle_cl_deps': False,
      'checkout_angle_dawn_deps': False,
      'checkout_angle_internal': False,
      'checkout_angle_mesa': False,
      'checkout_angle_partition_alloc': False,
      'checkout_angle_perfetto': False,
      'checkout_angle_restricted_traces': False,
      'checkout_extra_traces': False,
    },
  },
]
"""
    (source_dir / ".gclient").write_text(gclient_config)

    env = os.environ.copy()
    env["DEPOT_TOOLS_UPDATE"] = "0"
    env["PATH"] = f"{depot_tools_dir}{os.pathsep}{env.get('PATH', '')}"
    run_command(
        [str(depot_tools_dir / "ensure_bootstrap")],
        cwd=depot_tools_dir,
        env=env,
    )
    run_command(
        [str(depot_tools_dir / "gclient"), "sync", "--no-history"],
        cwd=source_dir,
        env=env,
    )
    return source_dir, depot_tools_dir, env


def normalize_arch(platform, arch):
    if arch in ("x64", "x86_64"):
        return "x64"
    if arch in ("arm64", "aarch64"):
        return "arm64"
    print(f"Error: unsupported {platform} architecture: {arch}")
    sys.exit(1)


def gn_args(target_platform, arch, config):
    args = {
        "angle_build_tests": False,
        "angle_enable_cl": False,
        "angle_enable_commit_id": False,
        "angle_enable_gl": False,
        "angle_enable_perfetto": False,
        "angle_enable_null": False,
        "angle_enable_swiftshader": False,
        "angle_enable_wgpu": False,
        "angle_has_frame_capture": False,
        "clang_use_chrome_plugins": False,
        "is_component_build": False,
        "is_debug": config == "Debug",
        "is_official_build": False,
        "symbol_level": 0,
        "target_cpu": arch,
        "target_os": target_platform,
        "use_remoteexec": False,
    }
    if target_platform == "linux":
        args.update(
            {
                "angle_enable_metal": False,
                "angle_enable_vulkan": True,
                "angle_use_custom_libvulkan": False,
                "angle_use_wayland": True,
                "angle_use_x11": True,
                "use_sysroot": True,
            }
        )
    else:
        args.update(
            {
                "angle_enable_metal": True,
                "angle_enable_vulkan": False,
                "angle_use_wayland": False,
                "angle_use_x11": False,
            }
        )

    values = []
    for key, value in sorted(args.items()):
        if isinstance(value, bool):
            encoded = "true" if value else "false"
        elif isinstance(value, int):
            encoded = str(value)
        else:
            encoded = f'"{value}"'
        values.append(f"{key}={encoded}")
    return " ".join(values)


def build_arch(source_dir, depot_tools_dir, env, target_platform, arch, config):
    if target_platform == "linux":
        run_command(
            [
                "python3",
                str(source_dir / "build/linux/sysroot_scripts/install-sysroot.py"),
                f"--arch={arch}",
            ],
            cwd=source_dir,
            env=env,
        )

    output_dir = source_dir / "out" / f"{target_platform}-{arch}-{config.lower()}"
    run_command(
        [
            str(depot_tools_dir / "gn"),
            "gen",
            str(output_dir),
            f"--args={gn_args(target_platform, arch, config)}",
        ],
        cwd=source_dir,
        env=env,
    )
    run_command(
        [
            str(depot_tools_dir / "autoninja"),
            "-C",
            str(output_dir),
            "libEGL",
            "libGLESv2",
        ],
        cwd=source_dir,
        env=env,
    )
    return output_dir


def copy_headers(source_dir, package_dir):
    include_dir = package_dir / "include"
    if include_dir.exists():
        shutil.rmtree(include_dir)
    include_dir.mkdir(parents=True)
    for name in ("EGL", "GLES2", "GLES3", "KHR"):
        shutil.copytree(source_dir / "include" / name, include_dir / name)
    shutil.copy2(source_dir / "LICENSE", package_dir / "LICENSE.angle")


def copy_runtime(output_dir, package_dir, target_platform):
    lib_dir = package_dir / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".dylib" if target_platform == "mac" else ".so"
    for name in (f"libEGL{suffix}", f"libGLESv2{suffix}"):
        source = output_dir / name
        if not source.exists():
            print(f"Error: expected ANGLE runtime not found: {source}")
            sys.exit(1)
        shutil.copy2(source, lib_dir / name)


def main():
    args = parse_args()
    require_host(args.platform)

    root_dir = Path(__file__).parent.absolute()
    build_dir = Path(args.out).absolute()
    source_dir, depot_tools_dir, env = ensure_sources(root_dir, args.revision)

    archs = [
        normalize_arch(args.platform, arch.strip()) for arch in args.archs.split(",")
    ]
    for arch in archs:
        print(f"Building ANGLE for {args.platform} {arch} ({args.config})")
        output_dir = build_arch(
            source_dir, depot_tools_dir, env, args.platform, arch, args.config
        )
        package_dir = build_dir / f"angle-{args.platform}-{arch}"
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True)
        copy_headers(source_dir, package_dir)
        copy_runtime(output_dir, package_dir, args.platform)
        (package_dir / "ANGLE_REVISION").write_text(f"{args.revision}\n")
        print(f"Packaged ANGLE at {package_dir}")


if __name__ == "__main__":
    main()
