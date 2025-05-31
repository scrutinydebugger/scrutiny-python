__all__ = [
    '__name__',
    '__version__',
    '__author__',
    '__credits__',
    '__license__',
    '__status__',
    'compiled',
    'get_shell_entry_point', 
    ]


__name__ = 'scrutiny'
__version__ = '0.4.3'
__author__ = 'Scrutiny Debugger'
__credits__ = ['Pier-Yves Lessard', 'Frédéric Morin', 'Joel Viau', 'Antoine Robidoux']
__license__ = 'MIT'
__status__ = 'Development'

compiled = "__compiled__" in globals()


import sys
import os
import shutil
from typing import List, Optional, Dict

if sys.platform == 'win32':
    CLI_EXECUTABLE_POSSIBLE_NAMES = [f"{__name__}.exe"]
else:
    CLI_EXECUTABLE_POSSIBLE_NAMES = [__name__, f"{__name__}.bin"]   

def get_shell_entry_point(env:Optional[Dict[str,str]]=None) -> Optional[List[str]]:
    if not compiled:
        if env is not None:
            if 'PYTHONPATH' not in env:
                env['PYTHONPATH'] = ''
            # Make sure we run exactly the same installation of scrutiny
            env['PYTHONPATH'] = os.path.dirname(__file__) + ':' +  env['PYTHONPATH']
        return [sys.executable, '-m', 'scrutiny']
    
    # Compiled
    caller = sys.argv[0]
    caller_dir = os.path.dirname(caller)
    caller_basename = os.path.basename(caller)

    if caller_basename in CLI_EXECUTABLE_POSSIBLE_NAMES:
        return [os.path.normpath(os.path.abspath(caller))]
    
    for executable_name in CLI_EXECUTABLE_POSSIBLE_NAMES:
        same_dir_candidate = os.path.join(caller_dir, executable_name)
        if os.path.isfile(same_dir_candidate):
            return [os.path.normpath(os.path.abspath(same_dir_candidate))]

    for executable_name in CLI_EXECUTABLE_POSSIBLE_NAMES:
        executable = shutil.which(executable_name)
        if executable is not None:
            return [executable]
    
    return None
