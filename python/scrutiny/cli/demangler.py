import subprocess

class GccDemangler:      

    def demangle(self, mangled):
        self.process = subprocess.Popen('c++filt --format gnu-v3 -n', stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True)
        return self.process.communicate(input=mangled)[0]
