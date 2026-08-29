#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <EGL/eglext_angle.h>
#include <GLES3/gl3.h>

#include <array>
#include <cstring>
#include <iostream>
#include <string>

namespace {

bool checkShader(GLuint shader) {
    GLint compiled = GL_FALSE;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
    if (compiled == GL_TRUE) {
        return true;
    }

    GLint length = 0;
    glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &length);
    std::string log(static_cast<size_t>(length), '\0');
    glGetShaderInfoLog(shader, length, nullptr, log.data());
    std::cerr << "Shader compilation failed: " << log << std::endl;
    return false;
}

}  // namespace

int main() {
    auto getPlatformDisplay = reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(
        eglGetProcAddress("eglGetPlatformDisplayEXT"));
    if (!getPlatformDisplay) {
        std::cerr << "eglGetPlatformDisplayEXT is unavailable" << std::endl;
        return 1;
    }

#if defined(__APPLE__)
    constexpr EGLint renderer = EGL_PLATFORM_ANGLE_TYPE_METAL_ANGLE;
#else
    constexpr EGLint renderer = EGL_PLATFORM_ANGLE_TYPE_VULKAN_ANGLE;
#endif
    const EGLint displayAttributes[] = {
        EGL_PLATFORM_ANGLE_TYPE_ANGLE,
        renderer,
#if !defined(__APPLE__)
        EGL_PLATFORM_ANGLE_NATIVE_PLATFORM_TYPE_ANGLE,
        EGL_PLATFORM_SURFACELESS_MESA,
#endif
        EGL_NONE,
    };
    EGLDisplay display = getPlatformDisplay(
        EGL_PLATFORM_ANGLE_ANGLE, EGL_DEFAULT_DISPLAY, displayAttributes);
    if (display == EGL_NO_DISPLAY || !eglInitialize(display, nullptr, nullptr)) {
        std::cerr << "ANGLE display initialization failed: 0x" << std::hex
                  << eglGetError() << std::endl;
        return 2;
    }

    const EGLint configAttributes[] = {
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_NONE,
    };
    EGLConfig config = nullptr;
    EGLint configCount = 0;
    if (!eglChooseConfig(display, configAttributes, &config, 1, &configCount) ||
        configCount == 0) {
        std::cerr << "ANGLE framebuffer selection failed" << std::endl;
        eglTerminate(display);
        return 3;
    }

    const EGLint contextAttributes[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_CONTEXT_WEBGL_COMPATIBILITY_ANGLE, EGL_TRUE,
        EGL_ROBUST_RESOURCE_INITIALIZATION_ANGLE, EGL_TRUE,
        EGL_NONE,
    };
    EGLContext context = eglCreateContext(
        display, config, EGL_NO_CONTEXT, contextAttributes);
    const EGLint surfaceAttributes[] = {
        EGL_WIDTH, 64,
        EGL_HEIGHT, 64,
        EGL_NONE,
    };
    EGLSurface surface = eglCreatePbufferSurface(
        display, config, surfaceAttributes);
    if (context == EGL_NO_CONTEXT || surface == EGL_NO_SURFACE ||
        !eglMakeCurrent(display, surface, surface, context)) {
        std::cerr << "ANGLE context creation failed: 0x" << std::hex
                  << eglGetError() << std::endl;
        if (surface != EGL_NO_SURFACE) {
            eglDestroySurface(display, surface);
        }
        if (context != EGL_NO_CONTEXT) {
            eglDestroyContext(display, context);
        }
        eglTerminate(display);
        return 4;
    }

    const char *rendererName = reinterpret_cast<const char *>(
        glGetString(GL_RENDERER));
    if (!rendererName || std::strstr(rendererName, "ANGLE") == nullptr) {
        std::cerr << "Unexpected renderer: "
                  << (rendererName ? rendererName : "unavailable") << std::endl;
        return 5;
    }
    std::cout << "Renderer: " << rendererName << std::endl;

    constexpr const char *vertexSource = R"GLSL(#version 300 es
in vec2 position;
void main() {
    gl_Position = vec4(position, 0.0, 1.0);
}
)GLSL";
    constexpr const char *fragmentSource = R"GLSL(#version 300 es
precision highp float;
out vec4 color;
void main() {
    color = vec4(1.0, 0.0, 0.0, 1.0);
}
)GLSL";

    const GLuint vertexShader = glCreateShader(GL_VERTEX_SHADER);
    glShaderSource(vertexShader, 1, &vertexSource, nullptr);
    glCompileShader(vertexShader);
    const GLuint fragmentShader = glCreateShader(GL_FRAGMENT_SHADER);
    glShaderSource(fragmentShader, 1, &fragmentSource, nullptr);
    glCompileShader(fragmentShader);
    if (!checkShader(vertexShader) || !checkShader(fragmentShader)) {
        return 6;
    }

    const GLuint program = glCreateProgram();
    glAttachShader(program, vertexShader);
    glAttachShader(program, fragmentShader);
    glLinkProgram(program);
    GLint linked = GL_FALSE;
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    if (linked != GL_TRUE) {
        std::cerr << "Shader program linking failed" << std::endl;
        return 7;
    }
    glUseProgram(program);

    constexpr std::array<float, 6> vertices = {
        0.0f, 0.8f, -0.8f, -0.8f, 0.8f, -0.8f,
    };
    GLuint buffer = 0;
    glGenBuffers(1, &buffer);
    glBindBuffer(GL_ARRAY_BUFFER, buffer);
    glBufferData(GL_ARRAY_BUFFER, sizeof(vertices), vertices.data(),
                 GL_STATIC_DRAW);
    const GLint position = glGetAttribLocation(program, "position");
    glEnableVertexAttribArray(static_cast<GLuint>(position));
    glVertexAttribPointer(static_cast<GLuint>(position), 2, GL_FLOAT, GL_FALSE,
                          0, nullptr);

    glViewport(0, 0, 64, 64);
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    glFinish();

    std::array<unsigned char, 4> pixel = {};
    glReadPixels(32, 32, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel.data());
    std::cout << "Center pixel: " << static_cast<int>(pixel[0]) << ", "
              << static_cast<int>(pixel[1]) << ", "
              << static_cast<int>(pixel[2]) << ", "
              << static_cast<int>(pixel[3]) << std::endl;

    eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
    eglDestroySurface(display, surface);
    eglDestroyContext(display, context);
    eglTerminate(display);

    if (pixel[0] < 200 || pixel[1] > 20 || pixel[2] > 20 || pixel[3] < 200) {
        std::cerr << "ANGLE rendered an unexpected center pixel" << std::endl;
        return 8;
    }
    return 0;
}
