import os

POST_HEADERS = {'content-type': 'application/json', 'accept': 'application/json'}

def run_cmd(cmd, work_dir=None, fail=True):
    """Run the specified command. If fail == True, and a non-zero exit value 
       is returned from the process, raise an exception
    """
    old_dir = os.getcwd()
    if work_dir is not None:
        os.chdir(work_dir)

    try:
        print(cmd)
        ret = os.system(cmd)
        if ret != 0:
            print("Error running command: %s (return value: %s)" % (cmd, ret))
            if fail:
                raise Exception("Failed to run: '%s' (return value: %s)" % (cmd, ret))
    finally:
        if work_dir is not None:
            os.chdir(old_dir)


