import logging
import os
import pathlib
import subprocess
import sys
import tempfile


def call(cmd):
    """
    Calls a python2 command in a subprocess

    Commands with quoted strings should be escaped before passing into this function
    """
    if sys.platform == "win32":
        logging.warning("Python2-wrapper call not yet implemented for windows")
        return -1
    elif not os.path.exists("/usr/bin/pythonw") and not os.path.exists("/usr/local/bin/pythonw"):
        logging.warning("Python2-wrapper cannot be found. Returning -1.")
        return -1

    this_dir = str(pathlib.Path(os.path.dirname(__file__), "..").resolve())
    cmd = "import sys; sys.path.append(\""+this_dir+"\");"+cmd

    # Write out temp .py file to avoid quotation clashes
    # cmd = "pythonw -c '"+cmd+"'"
    fd, temp_py = tempfile.mkstemp(suffix=".py", text=True)
    with open(temp_py, "w") as f:
        f.write(cmd)
    cmd = "pythonw '"+temp_py+"'"

    logging.debug(cmd)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, executable='/bin/sh')

    proc.wait()
    proc.stdout.close()
    return_value = proc.returncode
    proc.kill()
    if os.path.isfile(temp_py):
        os.remove(temp_py)
    return return_value
