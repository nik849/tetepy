# This file is part of the TeTePy software
# 
# Copyright (c) 2017, 2018, University of Southampton
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os, datetime, subprocess, time, re, exceptions, sys, tempfile, logging, shutil, errno, glob
run_constrained_pytest_exe = os.path.expanduser("~/code/c/run_constrained_pytest")
assert os.path.exists(run_constrained_pytest_exe),"Missing executable for constrained execution"

if __name__=="__main__":
    import logging
    sys.path.append(os.path.join(os.getcwd(),".."))

from lab_helpers import PyTestException,RunConstrainedException

statusfilename='status.txt'
pytest_stdout='pytest.stdout'
pytest_stderr='pytest.stderr'
pytest_log='pytest_log'

#by default, do not use rst format
rst_format=False #new feature for rst2html (Jan 2010)

from enqueue_outgoing_mails import send_text_message

try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()

conf = __import__('config_' + Modulecode.lower())


def copy_helper(source, dest, log_global):
    """ Calls shutil.copy() to copy source to dest, checks for
    errors, logs the attempt and if an error results, logs that
    too. """

    # shutils.copy() copies the permission bits of the original file.
    log_global.debug("Trying to copy {0} to {1}".format(source, dest))
    try:
        shutil.copy(source, dest)
    except IOError as e:
        log_global.critical("IOError({0}): {1} copying {2} to {3}".format(e.errno, e.strerror, source, dest))
        raise
    except:
        log_global.critical("Unknown error copying {0} to {1}".format(source, dest))
        raise

def run_time_limited_subprocess(command, maxseconds,check_dt=0.1,kill_dt=0.1):
    s = subprocess.Popen(command,shell=True,stderr=subprocess.PIPE,stdout=subprocess.PIPE)

    start = time.time()

    while s.poll() == None: #subprocess still busy
        time.sleep(check_dt)
        if time.time()-start > maxseconds:
            if s.poll() == None:
                os.kill(s.pid,9)
                s.wait()
                break

    return s


def run_pytest(submissionfilepath, testfilepath, log_global, jobfilepath=None, rundirectoryname=None, 
               rundirectorypath=None,maxseconds=10):
    """Given a submissionfilepath (that is the path of the file coming from the student) 
    and the path of the test_*.py file, it will copy the submission filename into a
    new directory under the name 's.py'. The test_*.py file has to import from s.py.

    The new directory carries the date and time unless RUNDIRECTORYNAME is specified,
    and is placed in RUNDIRECTORYPATH

    Returns the directory in which the test have been run.

    The jobfile is the meta-data about this job, and kept for debugging and logging purposes.
    If None, this will be ignored.
    """

    testfiledir,testfilename=os.path.split(os.path.abspath(testfilepath))

    assert testfilename != 's.py', "Testing filename must not be submission filename (s.py)"

    if rundirectoryname == None:
        d=datetime.datetime.now();
        rundirectoryname = "_test-"+d.strftime("%Y-%m-%d-%H:%M:%S")

    if rundirectorypath == None:
        rundirectorypath = ''

    rundirectory = os.path.join(rundirectorypath,rundirectoryname)

    def path(fname):
        return os.path.join(rundirectory,fname)

    assert os.system("mkdir -p %s" % rundirectory) == 0

    if jobfilepath:
        copy_helper(jobfilepath, rundirectory, log_global)

    copy_helper(submissionfilepath, path("s.py"), log_global)
    copy_helper(testfilepath, path(testfilename), log_global)

    cmd = "cd %s && py.test -p resultlog --resultlog=%s %s > %s 2> %s" % (
        path(''), pytest_log,testfilename, pytest_stdout, pytest_stderr)

    open(path('pytest.command'),'a').write(cmd+"\n")

    log_global.debug("Executing '%s'" % cmd)

    subprocess = run_time_limited_subprocess(cmd,maxseconds=maxseconds)

    assert subprocess.returncode != None,"Subprocess (%s) hasn't terminated return -- should be impossible" % cmd

    if subprocess.returncode < 0:
        log_global.info("WARNING: code to be tested didn't termine within given time limit")
        open(path(statusfilename),'a').write("fail::%s::unterminated::\n" %  (datetime.datetime.now().isoformat()))
    elif subprocess.returncode in [0,1]: #all okay, 1 signals that at least one test has failed
        open(path(statusfilename),'a').write("okay::%s::retcode=%d\n" % (datetime.datetime.now().isoformat(),subprocess.returncode))
    elif subprocess.returncode >1: #some py.test reported problem
        open(path(statusfilename),'a').write("fail::%s::retcode=%d\n" % (datetime.datetime.now().isoformat(),subprocess.returncode))
        raise PyTestException, "Py.test reports an error when running '%s' (returncode=%s)" % (cmd,subprocess.returncode)

    return rundirectory


def run_pytest_constrained(submissionfilepath, testfilepath, log_global,
                           other_submitted_filepaths=[],
                           rundirectoryname=None, 
                           rundirectorypath=None, jobfilepath=None,
                           maxseconds=10, pytest_args='',):
    """
    Run py.test on a given test_*.py file to analyse some piece of code.
    Do this in a sandboxed-environment. If it is Python code, the piece of
    code to be tested needs to be provided as 'submissionfilepath' and 
    will be copied as s.py into the testing directory. The testing code
    test_*.py thus needs to import from s.py.

    For testing of c-code, this is different, and the submissionfilepath should 
    be set to None. The c-codes to test (one or more files), need to be passed 
    as 'other_submitted_filepaths' (see below).

    Parameters
    ----------
      submissionfilepath : str or None
        path to the file to be tested. For example, the file could be 
        training1.py or /tmp/noeunth2ntho/training1.py

      testfilepath : str
        path to the test_*.py file that contains the tests to be run.
        For example 'test_training1.py'.

      log_global : logging.Logger
        logger to log progress to

      other_submitted_filepaths : list of str
        list of additional files (in addition to the submissionfilepath)
        that are used by the test_*.py file in testing, and which need to be 
        copied from the location given as parameters to the temporary directory
        in which the testing takes place.

      rundirectoryname : str on None
        directory in which the testing should take place

      rundirectorypath : str or None 
        full path to directory in which testing should take place

      jobfilepath : str or None
        pull path to job summary file. If given, will be copied to testing 
        directory, but not required to provide.

      maxseconds : int or float
        Argument to time.sleep that specifies the maximum number of seconds
        a testing script is allowed to run.

      pytest_args : str
        Additional arguments to be given to py.test. For C-code testing, this
        might include ...?

    Returns
    -------

       resultdirectory : str
         path to directory that contains test files

    Additional info
    ---------------

    Given a submissionfilepath (that is the path of the file coming from the student) 
    and the path of the test_*.py file, it will copy the submission filename into a
    tmp directory under the name 's.py'. The test_*.py file has to import from s.py.

    TODO: change submissionfilepath into list of files
       Update: Actually, we can work around this: the submissionfilepath and 
       'other_submitted_filepaths' are treated the same. The difference is that
       the 'submissionfilepath' is the one copied to 's.py'.

    We then run the py.test call in that tmp directory, and copy the output to a new directory.
    The new directory carries the date and time unless RUNDIRECTORYNAME is specified,
    and is placed in RUNDIRECTORYPATH

    Returns the directory in which the test results are stored.
    """

    # extract the files that contains thetests
    testfiledir,testfilename=os.path.split(os.path.abspath(testfilepath))

    # student file by convention will be called s.py. If the file with the
    # tests has the same name, then the student file would override the test
    # file when copied to the temporary directory. So we don't allow this.
    assert testfilename != 's.py', "Submission filename must not be solution.py"

    if rundirectoryname == None:
        d=datetime.datetime.now();
        rundirectoryname = "_test-"+d.strftime("%Y-%m-%d-%H:%M:%S")

    if rundirectorypath == None:
        rundirectorypath = ''

    resultdirectory = os.path.join(rundirectorypath,rundirectoryname)

    id1 = os.getenv("USER")
    id3 = os.getenv("HOME").split('/')[-1] # risky, as split could act on None
    id4 = str(os.getuid()) 

    ids = [id1, id3, id4]

    #get rid of those that return None
    ids = [id for id in ids if id is not None]
    assert len(ids) > 0, "Could not identify user name or id -- why?"
    # use first entry
    username = ids[0]

    assert username != None, "Couldn't find USER environment variable"

    # create testing directories PER user, i.e. per teaching module
    tmpprefixpath = os.path.join("/tmp/pytest-"+str(username)+'/')
    if not os.path.exists(tmpprefixpath):
        log_global.info("Creating path %s")
        os.makedirs(tmpprefixpath)
        os.chmod(tmpprefixpath, 0774)  # must be writable and usable by group (run_stud) 

    tmprundirectory =  tempfile.mkdtemp(prefix=tmpprefixpath)
    log_global.debug("tmp path for constrained testing is '%s'" % tmprundirectory)

    # Convenience function 'path' that, give a file name, returns the full
    # path to that filename in the place where we run the tests.
    def path(fname):
        return os.path.join(tmprundirectory,fname)


    # the run_stud executable will run with the id of user run_stud. To
    # be allowed to write to the temporary directory, we need to give
    # give permission for this. First, make the unix group of the directory
    # to be run_stud's group:
    cmd = 'chgrp run_stud %s' % (tmprundirectory)
    log_global.debug(cmd)
    # if the this fails, we need to check the right cross-wise group member ship between
    # the account with the module code (for example sesa2006) and the account to run
    # the code (run_stud). It appears both need to be members of the other group to allow
    # the chgrp command.

    try:
        assert os.system(cmd) == 0,"Error executing '%s'" % cmd
    except AssertionError, msg:
        mymsg = "If this fails, it could mean that the current user is not in the"+\
            "run_stud group and vice versa (check in /etc/group)."
        mymsg += "The error we caught was \n\t{}".format(msg)
        print(mymsg)
        log_global.error(mymsg)
        raise
    # Then make sure that the group has execute and write rights in that subdir
    cmd = 'chmod 2770 %s' % (tmprundirectory)
    log_global.debug(cmd)
    assert os.system(cmd) == 0, "Error executing '%s'" % cmd

    #the list of files that contains the tests to be carried out (typically having
    #names starting with 'test_'. We use only one file at the moment.
    for f in [testfilepath]:
        copy_helper(f, tmprundirectory, log_global)

    # if given, copy job summary file into testing directory. Do this 
    # before copying any other files (this is the file we can lose as it provides
    # redundant information, albeit in a convenient location.)
    if jobfilepath:
        copy_helper(jobfilepath, tmprundirectory, log_global)

    # If submissionfilepath is specified, then copy the student's submission. 
    # This would nomally be done
    # for Python testing: the student submits lab1.py, the file with the tests
    # is test_lab1.py, and we then copy lab1.py to s.py.

    # For testing of C-code, set submissionfilepath to None, and put the c-files
    # as other-studentfiles, or so.

    if submissionfilepath != None:
        if os.path.exists(submissionfilepath):
            copy_helper(submissionfilepath, path("s.py"), log_global)
        else:
            #we should never get to this point as the testing should not be executed if the student submitted
            #file is missing.
            log_global.warn("Didn't find student submission file '%s'" % submissionfilepath)
            raise RuntimeError,"This should be impossible -- where is the file '%s' (-> s.py)" % submissionfilepath
    else:
        log_global.debug("Looks like we are assessing C code as no submission filepath was provided.")
        assert len(other_submitted_filepaths) > 0, "Need some files to test, no?"

    #Any other files that the student should have submitted (data files, plots, etc)
    #which the testing script may decide to look into.

    for tmp_f in other_submitted_filepaths:
        targetname = path(os.path.split(tmp_f)[1])
        if os.path.exists(tmp_f):
            log_global.debug("File %s exists: -> cmd = %s " % (tmp_f,cmd))
            copy_helper(tmp_f, targetname, log_global)

            # need to change permissions of these extra files, so that students can override
            # them if necessary. We do this by making them group writable. The files owner
            # is the module account, the group is 'run_stud'.
            log_global.debug("Trying to change file (%s) mod to be group writable" % targetname)
            try:
                os.chmod(targetname, 0664)
            except:
                log_global.debug("Cannot set mode of file %s" % targetname)
                raise
        else:
            log_global.debug("File %s is not there. Not submitted by student. Not copying to testing directory" % tmp_f)

    #actual execution of testing procedure
    cmd = "cd %s && %s %s -p resultlog --resultlog=%s %s > %s 2> %s" % (
        path(""), run_constrained_pytest_exe, path(testfilename),
        pytest_log, pytest_args, pytest_stdout, pytest_stderr)

    open(path('pytest.command'),'a').write(cmd+"\n")

    log_global.debug("Executing '%s'" % cmd)

    subprocess  = run_time_limited_subprocess(cmd, maxseconds=maxseconds)

    assert subprocess.returncode!=None,"Subprocess (%s) hasn't terminated return -- should be impossible" % cmd

    log_global.debug( "subprocess.returncode=%d" % subprocess.returncode)

    if subprocess.returncode < 0:
        log_global.info("WARNING: code to be tested didn't terminate within given time limit")
        open(path(statusfilename),'a').write("fail::%s::unterminated::\n" %  (datetime.datetime.now().isoformat()))
    elif subprocess.returncode in [0]: #all okay, 
        open(path(statusfilename),'a').write("okay::%s::retcode=%d\n" % (datetime.datetime.now().isoformat(),subprocess.returncode))
    elif subprocess.returncode == 1: # some run_constrained reported problem
        open(path(statusfilename),'a').write("fail::%s::retcode=%d:violation?\n" % (datetime.datetime.now().isoformat(),subprocess.returncode))
        raise RunConstrainedException, "Run_constrained reports an error when running '%s' (returncode=%s)" % (cmd,subprocess.returncode)
    elif subprocess.returncode >= 2: # not sure what this means
        open(path(statusfilename),'a').write("fail::%s::retcode=%d:?\n" % (datetime.datetime.now().isoformat(),subprocess.returncode))
        raise StandardError, "Should be impossible: running '%s' results in returncode=%s" % (cmd,subprocess.returncode)


    # Now remove the group-access bits in the temporary directory's
    # permissions; this prevents code tested in the future from being able to
    # read this directory (as the owner will be the course-user, not run_stud;
    # access via run_stud relies on the group permissions alone).
    res = os.system('chmod =0700 %s' % tmprundirectory)
    log_global.debug("Tried to chmod the directory {0} to =0700, return status was {1}".format(tmprundirectory,res))

    #then copy over
    log_global.debug("Trying to copy all files from {0} to {1}".format(path("*"), resultdirectory))
    try:

        # No need to make directory; shutil.copytree() says
        # destination dir must not exist.  Check it does not exist
        # first.
        if(os.path.isdir(resultdirectory)):
            resultdirectory_newname = resultdirectory + str(time.time())
            log_global.error("Results directory {0} already exists, probably due to previous failure of testing code or run_constrained_pytest and subsequent unlock".format(resultdirectory))
            log_global.info("Renaming {0} to {1} ".format(resultdirectory, resultdirectory_newname))
            os.rename(resultdirectory, resultdirectory_newname)

        # Now, continue to copy in our files to test.
        shutil.copytree(path(""), resultdirectory)

    except:
        log_global.critical("Cannot copy all files from {0} to {1}.".format(path("*"),resultdirectory))
        raise
    #and return location of this directory.
    return resultdirectory


if __name__=="__main__":

    Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()
    conf = __import__('config_' + Modulecode.lower())

    log_global  = logging.getLogger('root')  

    import enqueue_outgoing_mails
    enqueue_outgoing_mails.log_global = log_global
    enqueue_outgoing_mails.conf = conf

    import post_test_analysis
    post_test_analysis.conf = conf

    tests = [("test-all-ok","tests/tenfunc_correct.py"),
             ("test-some-fail","tests/tenfunc_with_errors.py"),
             ("test-hang","tests/tenfunc_with_hang.py"),
             ("test-write","tests/tenfunc_writefile.py"),
             ("test-write-naughty","tests/tenfunc_writefile2.py"),
             ("test-import-fails","tests/tenfunc_importfails.py"),
             ("test-import-fails2","tests/tenfunc_importfails2.py"),
             ("test-infinite-loop","tests/tenfunc_infiniteloop.py"),
             ("test-all-ok","tests/tenfunc_correct.py")
             ]

    for dir,testfile in tests:

        print "Testing file '%s' in directory '%s'" % (testfile,dir)

        rundir=run_pytest_constrained(testfile,'tests/test_tenfunc.py',logging,\
                                      rundirectorypath=os.getcwd(),rundirectoryname=dir)

        #analyse outcome
        a,status=conf.parse_pytest_report(rundir, log_global)
        if status == False:
            print "WARN: test file didn't return, need manual treatment for test in '%s'" % rundir
            print "status=%s" % status
            print "a=%s" % a
        else:
            print conf.pass_fail_total(a)
            print conf.summary_text(a)
