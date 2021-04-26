import sys,os,glob, subprocess, shutil
import os
import subprocess
import datetime

def do_reduction(path,outdir):
    reduction_files=glob.glob(os.path.join(outdir,'reduce_HYS_*.py'))
    default_reduction_files=glob.glob(os.path.join('/SNS/HYS/shared/templates/reduce_HYS_*.py'))
    latest_default_reduction=max(default_reduction_files,key=os.path.getmtime)
    now = datetime.datetime.now().strftime('%Y-%m-%d_%H:%M')
    filename = os.path.join(outdir, f'reduce_HYS_{now}.py')
    if reduction_files!=[]:
        latest_reduction=max(reduction_files,key=os.path.getmtime)
        if os.path.getmtime(latest_reduction)<os.path.getmtime(latest_default_reduction):
            latest_reduction=filename
            shutil.copy2(latest_default_reduction, latest_reduction)
    else:
        latest_reduction=filename
        shutil.copy2(latest_default_reduction, latest_reduction)
    cmd = "python3 {0} {1} {2}".format(latest_reduction, path, outdir)
    proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                            universal_newlines = True,
                            cwd=outdir)
    proc.communicate()



if __name__ == "__main__":
    #check number of arguments
    if (len(sys.argv) != 3):
        print("autoreduction code requires a filename and an output directory")
        sys.exit()
    if not(os.path.isfile(sys.argv[1])):
        print("data file ", sys.argv[1], " not found")
        sys.exit()
    else:
        path = sys.argv[1]
        out_dir = sys.argv[2]
        do_reduction(path, out_dir)
