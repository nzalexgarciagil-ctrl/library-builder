# Mystral Engine Library Builder

This repository provides automated builds of native libraries for [Mystral Engine](https://github.com/mystralengine) dependencies.

**Currently supported:**
- [Skia](https://skia.org/) - 2D graphics library with Dawn/Graphite support
- [libwebp](https://chromium.googlesource.com/webm/libwebp/) - WebP codec to encode & decode images in WebP format
- [swc](https://github.com/swc-project/swc) - Speedy Web Compiler to compile typescript.
- [libuv](https://libuv.org/) - Async I/O event loop (non-blocking network, file, timers).
- [Draco](https://github.com/google/draco) - Mesh compression (native glTF Draco decoding).
- [quiche](https://github.com/cloudflare/quiche) - QUIC + HTTP/3, the native backend for the WebTransport API. Built with the `ffi` feature plus a small patch exposing WebTransport SETTINGS; bundles BoringSSL.
- [ANGLE](https://chromium.googlesource.com/angle/angle) - EGL and OpenGL ES shared runtimes for WebGL 2. Linux packages use Vulkan with X11 and Wayland; macOS packages use Metal.

**Planned:**
- V8 - JavaScript engine. Currently using older build from https://github.com/kuoruan/libv8

**Dependencies with existing prebuilt libraries**
- Dawn - https://github.com/google/dawn/releases - Google / Chrome's WebGPU implementation. Note however that this doesn't have iOS releases, while the Skia build above does have a Dawn iOS release associated.
- wgpu-native - https://github.com/gfx-rs/wgpu-native - built from wgpu, a rust based implementation of WebGPU (webgpu.h) used in Firefox.
- SDL3 - https://github.com/libsdl-org/SDL/releases - Simple DirectMedia Layer - a cross-platform development library designed to provide low level access to audio, keyboard, mouse, joystick, and graphics hardware via OpenGL/Direct3D/Metal/Vulkan.

**Dependencies that don't need prebuilds**
- quickjs / quickjs-ng - https://github.com/quickjs-ng/quickjs - specifically ng because of Windows support which quickjs doesn't have.
- JSC - Javascript Core - only available on Mac / iOS (bun has a windows build, but can't find if it is available independently). Built into OS.

**Fork of:** [olilarkin/skia-builder](https://github.com/olilarkin/skia-builder)

## Pre-built Binaries

Download pre-built binaries from the [Releases](https://github.com/mystralengine/library-builder/releases) page.

**Weekly builds** run automatically on Monday at 9:00 AM UTC from Skia's `main` branch.

## Supported Platforms

| Platform | Architectures | GPU Backend | Notes |
|----------|---------------|-------------|-------|
| macOS | universal, arm64, x86_64 | Metal + Dawn | macOS 10.15+ |
| iOS | arm64 device, arm64+x86_64 simulator | Metal + Dawn | iOS 14.0+ |
| visionOS | arm64 device, arm64 simulator | Metal + Dawn | visionOS 1.0+ |
| Android | arm64, arm, x64 | Vulkan + Dawn | API 24+ |
| Windows | x64 | D3D + Dawn | Static (/MT) and dynamic (/MD) CRT |
| Linux | x64 | Vulkan + Dawn | |
| WebAssembly | wasm32 | WebGL/WebGPU | |

## Building Locally

Prerequisites: ninja, python3, cmake. On Windows, LLVM must be installed at `C:\Program Files\LLVM\`.

```bash
# May need to increase file limit on macOS first
ulimit -n 2048

# Build libraries
python3 build-skia.py mac                    # macOS universal
python3 build-skia.py ios                    # iOS
python3 build-skia.py visionos               # visionOS
python3 build-skia.py android                # Android arm64
python3 build-skia.py win                    # Windows x64 (static CRT)
python3 build-skia.py win -crt dynamic       # Windows x64 (dynamic CRT)
python3 build-skia.py linux                  # Linux x64
python3 build-skia.py wasm                   # WebAssembly
python3 build-skia.py xcframework            # Apple XCFramework

# Build ANGLE WebGL 2 runtimes (must run on the target operating system)
python3 build-angle.py linux -archs x64       # Vulkan, X11, and Wayland
python3 build-angle.py mac -archs arm64        # Metal
```

ANGLE packages are written to `build/angle-<platform>-<architecture>`. Linux runtimes use the host's Vulkan loader, Vulkan driver, and XCB runtime; Wayland presentation additionally uses the system Wayland runtime libraries. macOS libraries use relocatable `@rpath` install names and are ad-hoc signed after packaging. The macOS x64 package is cross-built on Apple Silicon and render-tested under Rosetta because GitHub's Intel runner does not expose Metal. The ANGLE workflow builds each package and verifies a headless triangle render with pixel readback before publishing it.

### Options

```bash
-config Debug|Release    # Build configuration (default: Release)
-branch <branch>         # Skia branch to build (default: main)
-archs <archs>          # Comma-separated architectures
-variant cpu|gpu        # Build variant (default: gpu)
-crt static|dynamic     # Windows CRT linkage (default: static)
-ndk <path>             # Android NDK path
--shallow               # Shallow clone for faster builds
```

### Examples

```bash
# Debug build
python3 build-skia.py mac -config Debug

# Specific Skia branch
python3 build-skia.py mac -branch chrome/m145

# Windows with dynamic CRT (for Dawn compatibility)
python3 build-skia.py win -crt dynamic

# Android for multiple architectures
python3 build-skia.py android -archs arm64,arm,x64
```

## CI / GitHub Actions

The workflow builds all platforms in parallel and creates releases.

### Trigger Builds

```bash
# Build all platforms (uses main branch by default)
gh workflow run build-skia.yml

# Build specific platform without release
gh workflow run build-skia.yml -f platforms=android -f skip_release=true

# Build with specific Skia branch
gh workflow run build-skia.yml -f skia_branch=chrome/m145

# Check status
gh run list
gh run view <run-id> --log-failed
```

### Workflow Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `skia_branch` | Skia branch to build | `main` |
| `platforms` | Platforms to build (comma-separated or `all`) | `all` |
| `skip_release` | Skip creating release | `false` |
| `test_mode` | Skip build, create dummy files | `false` |

## Windows CRT Notes

Windows builds are provided with both static and dynamic CRT:

- **Static CRT** (`/MT`, `/MTd`): Use with vcpkg `x64-windows-static` triplet
- **Dynamic CRT** (`/MD`, `/MDd`): Use with Dawn or other libraries that use dynamic CRT

Mixing CRT types will cause linker errors. Ensure all dependencies use the same CRT.

## Output Structure

```
build/
├── include/           # Headers
├── share/             # ICU data (icudtl.dat)
├── mac-gpu/lib/       # macOS libraries
├── ios-gpu/lib/       # iOS libraries
├── visionos-gpu/lib/  # visionOS libraries
├── android-gpu/lib/   # Android libraries
├── win-gpu/lib/       # Windows (static CRT)
├── win-gpu-md/lib/    # Windows (dynamic CRT)
├── linux-gpu/lib/     # Linux libraries
├── wasm-gpu/lib/      # WASM libraries
└── xcframework/       # Apple XCFramework
```

## License

Skia is licensed under the BSD-style license. See [Skia License](https://skia.org/docs/user/license/) for details.
