from OpenGL.GL import *


class Shader:
    def __init__(self, vertexPath: str, fragmentPath: str):
        try:
            vertexCode = open(vertexPath).read()
            fragmentCode = open(fragmentPath).read()

            vertex = glCreateShader(GL_VERTEX_SHADER)
            glShaderSource(vertex, vertexCode)
            glCompileShader(vertex)
            self.checkCompileErrors(vertex, "VERTEX")

            fragment = glCreateShader(GL_FRAGMENT_SHADER)
            glShaderSource(fragment, fragmentCode)
            glCompileShader(fragment)
            self.checkCompileErrors(fragment, "FRAGMENT")

            self.ID = glCreateProgram()
            glAttachShader(self.ID, vertex)
            glAttachShader(self.ID, fragment)
            glLinkProgram(self.ID)
            self.checkCompileErrors(self.ID, "PROGRAM")

            # delete the shaders as they're linked into our program now and no longer necessary
            glDeleteShader(vertex)
            glDeleteShader(fragment)

        except IOError:
            print("ERROR::SHADER::FILE_NOT_SUCCESFULLY_READ")

    def getProgram(self):
        return self.ID

    def use(self) -> None:
        glUseProgram(self.ID)

    def checkCompileErrors(self, shader: int, type: str) -> None:
        if type != "PROGRAM":
            success = glGetShaderiv(shader, GL_COMPILE_STATUS)
            if not success:
                infoLog = glGetShaderInfoLog(shader)
                print(
                    "ERROR::SHADER_COMPILATION_ERROR of type: "
                    + type
                    + "\n"
                    + infoLog.decode()
                    + "\n -- --------------------------------------------------- -- "
                )
        else:
            success = glGetProgramiv(shader, GL_LINK_STATUS)
            if not success:
                infoLog = glGetProgramInfoLog(shader)
                print(
                    "ERROR::PROGRAM_LINKING_ERROR of type: "
                    + type
                    + "\n"
                    + infoLog.decode()
                    + "\n -- --------------------------------------------------- -- "
                )
