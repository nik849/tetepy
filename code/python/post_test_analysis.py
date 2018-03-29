# This file is part of the TeTePy software
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


import copy
import os
import re
import logging
import pprint
import enqueue_outgoing_mails
import mylogger
import tetepy

try:
    import ctestlib
except ImportError, msg:
    import sys
    print("Could not import ctestlib -- please install via")
    print("cd ~; sudo sh bin/install-python-libs.sh")
    print(msg)
    sys.exit(1)    
    
conf = None

def read_status(dirpath):
    """DIRPATH is the Path to the directory where the tests have run.
    Returns (True,"") if test is passed or
    (False, REASON) if the test failed.
    """
    path = os.path.join(dirpath, conf.statusfilename)
    f=open(path,'r')
    lines = f.readlines()
    f.close()
    if lines[-1].split('::')[0]=='okay':
        return (True,"")
    elif lines[-1].split('::')[0]=='fail':
        reason = lines[-1].split('::')[2]
        return (False,reason)
    else:
        raise NotImplementedError, "This should be impossible"


def pass_fail_total(report_data):
    """
    Converts pass fail data into points.
    
    Parameters
    ----------
    
      report_data : list of tuples (see example)
      
    Returns
    -------
    
      (np, nf, ntotal) : tuple of 3 numbers
      
    Example
    -------
    
    An example value for ``report_data`` is ::
       
       [(True, 'test_training1.py::test_distance', None), 
        (True, 'test_training1.py::test_geometric_mean', None), 
        (True, 'test_training1.py::test_pyramid_volume', None)]

    The bool value in the triplet indicates that a test has passed,
    the string in the second item is the test carried out, and
    the final value would be the error messages if the test had failed,
    and is ``None`` if no problem occured, as in this example.
    
    This function converts these outcomes into points: historically,
    this was a matter of summing up the passed tests, and the total
    mark would be the ratio of the passed tests over the failed tests,
    and all numbers returned are integers. 

    As of October 2013, we are introducing weights for particular
    functions, so that we can give more marks to a successful compilation
    of C code, say, and less for each independent functionality test.
    
    """
    n_passed = len([x[0] for x in report_data if x[0]==True])
    n_failed = len([x[0] for x in report_data if x[0]==False])
    n_total = n_passed + n_failed
    return n_passed, n_failed, n_total


def parse_pytest_for_c(dirpath, log):
    tests, status = parse_pytest_report(dirpath, log)
    print("tests = {}".format(tests))
    print("status = {}".format(status))
    return tests, status


def parse_pytest_report(dirpath, log):
    """Given the path to a pytest-directory, returns a tuple (A,B). The first entry A is the 
    report_data data structure:
      list L of triplets t with
        t[0] = True if test passed, False if failed
        t[1] = one line describing test (for example test/test_tenfunc.py:test_count)
        t[2] = None if test passed, otherwise
               String (including newlines) with more detailed failure description

    The second entry B is a list of bools. These are 'True' if py.test
    terminated and False if it didn't.

    If py.test did not terminate, the test data will be incomplete, but it is
    still useful to see which tests have been passed.
    """

    status, reason = conf.read_status(dirpath)

    log.debug("In parse_pytest_report, dirpath=%s" % dirpath)
    log.debug("DD status=%s" % status)
    log.debug("DD reason=%s" % reason)

    tests = []
    path = os.path.join(dirpath,conf.pytest_log)
    f = open(path,'r')
    lines = f.readlines()
    f.close()
    n = len(lines)

    log.debug("Read {} lines from {}: \n'''{}'''".format(n, path, "\n".join(lines)))

    if reason == "unterminated": #this happened when a job didn't terminate
            error_report="""When trying to test your submission, the
            testing code did not terminate within 60 seconds.

            Either your code runs a very lengthy calculation, or is stuck
            in some infinite loop.

            We cannot assess and test your code appropriately if it
            does not return.

            Please fix the problem (i.e. identify where it gets
            stuck), and resubmit, and inform the laboratory leader about
            this. If you don't understand any of this, please get also
            in touch with a demonstrator or the laboratory leader.

            Debug information:
              status = %s
              reason = %s
              Content of pytest_log:\n--\n%s
            --
            """ % (status,reason,"\n".join(lines))

            tests.append((False,"unterminated problem in s.py",error_report))
            log.warn( "auto-testing-problem"+str(tests)+str(status)+"Job has not terminated, need manual intervention??")

            return tests,status
    else:
            pass
            log.debug("Normal branch, have terminated.")  


    # We may need this in two places further below
    error_report_import_failed =  """
    When trying to import your submission, we have encountered an error,
    and as a result, this submission has failed. A likely problem is
    non-ASCII characters in your submission, or a syntax error, or 
    an operation that is carried out when the file is imported and which
    fails.
    
    All testing will fail if the file cannot be imported. It is thus
    important to remove all such errors before submission.
    
    We suggest that you either:
    
    - Execute the file on its own to check no errors are reported.
    
    - Ensure that you are not trying access particular data files that you have
      on your computer - these will generally not be available for the testing 
      system.
    
    - remove any characters that are not encoded as ASCII, and re-sumbit
      the file, or
    
    - specify the encoding of the file in accordance with the advice at
      http://www.python.org/dev/peps/pep-0263/
    
      For example, add the following comment on the first line of your
      file:
    
      # coding=utf-8
    
    If the above makes no sense (either because you don't understand it,
    or because you do understand but find this does not match reality),
    then please contact a demonstrator or the laboratory leader about
    this.
    """


    #special case:
    bug_1_description="""September 2011. It seems that syntax errors of this type:

    def my_foo(x):
         y = x**2
        return y

    which would result in an "IndentationError: unindent does not match any outer indentation level"
    can hang the testing with py.test (version 1.3).

    Upgrading py.test to 2.1.2 'solved' the hang issue. Py.test still fails with this behaviour (see tests/import-fails2.py):

      -  pytest_log is an empty file
      
      -  std error contains:


           Traceback (most recent call last):
           File "/usr/bin/py.test", line 9, in <module>
           load_entry_point('pytest==2.1.2', 'console_scripts', 'py.test')()
           File "/usr/local/lib/python2.6/dist-packages/pytest-2.1.2-py2.6.egg/_pytest/core.py", line 457, in main
           <snip>
           
           res = method(**kwargs)
           File "/usr/local/lib/python2.6/dist-packages/pytest-2.1.2-py2.6.egg/_pytest/resultlog.py", line 92, in pytest_internalerror
           path = excrepr.reprcrash.path
           AttributeError: 'str' object has no attribute 'reprcrash'.readlines()

      - stdout contains

        ============================= test session starts ==============================
	platform linux2 -- Python 2.6.6 -- pytest-2.1.2
	collecting ... INTERNALERROR> Traceback (most recent call last):
	INTERNALERROR>   File "/usr/local/lib/python2.6/dist-packages/pytest-2.1.2-py2.6.egg/_pytest/main.py", line 67, in wrap_session
	INTERNALERROR>     doit(config, session)
	INTERNALERROR>   File "/usr/local/lib/python2.6/dist-packages/pytest-2.1.2-py2.6.egg/_pytest/main.py", line 95, in _main
	INTERNALERROR>     config.hook.pytest_collection(session=session)
	INTERNALERROR>   File "/usr/local/lib/python2.6/dist-packages/pytest-2.1.2-py2.6.egg/_pytest/core.py", line 411, in __call__
	INTERNALERROR>     return self._docall(methods, kwargs)
        <snip>
	INTERNALERROR>   File "/usr/local/lib/python2.6/dist-packages/pytest-2.1.2-py2.6.egg/_pytest/resultlog.py", line 84, in pytest_collectreport
	INTERNALERROR>     longrepr = str(report.longrepr.reprcrash)
	INTERNALERROR> AttributeError: CollectErrorRepr instance has no attribute 'reprcrash'
	INTERNALERROR>

    The detailed files are available in code/python/subtest/bugs/bug-archive-test-import-fails2-py2.1.2

    So py.test seems to be buggy and ONLY in combination with the --reportlog switch. Decativing this --reportlog,
    gives the right error message.

    We will try to catch this here and ask the user(=student) to make sure they can 'run' their file through the
    interpreter without getting an error message.

    """

    if n == 0: #the only case where we know this can happen is the bug 1 described above.
        log.info("n == 0: Reached branch for suspected BUG 1")

        #let's carry out more checks to see whether this is the case.
        pytest_stdout_string = open(os.path.join(dirpath,conf.pytest_stdout)).read()
        if "INTERNALERROR" in pytest_stdout_string:
            log.info("Found 'INTERNALERROR' in stdout --> supports suspected bug 1 with py.test 2.1 (try py.test --version)")
            odd=0
        else:
            log.warn("Expected 'INTERNALERROR' in stdout but couldn't find. Don't understand.")
            odd=1

        pytest_stderr_string = open(os.path.join(dirpath,conf.pytest_stderr)).read()

        if """AttributeError""" in pytest_stderr_string and "reprcrash" in pytest_stderr_string:
            log.info("Found 'AttributeError' in  stderr --> supports suspected bug 1 with py.test 2.1")
            odd += 0
        else:
            odd += 1
            log.warn("Expected 'AttributeError <...>` in stderr but couldn't find. Don't understand.")

        
        #Printinternalerror> AttributeError: CollectErrorRepr instance has no attribute 'reprcrash'

        assert status == True,"This must be true as the test has returned and was not killed."

        if odd==0: #clear case for Bug 1 -- no ODDities
            log.info("n == 0: We think import failed. ")

            error_report="""When trying to import your submission, we have
encountered an error, and as a result, this submission
has failed. A likely problem is indentation. 

You should find that Python reports some error 
(SyntaxError most likely) when you execute your file
MYFILE *before* submission (either by pressing F5 in IDLE,
or running "python MYFILE.py").

All testing will fail if the file cannot be imported. It
is thus important to remove all such errors before
submission.

If the above makes no sense (either because you don't understand
it, or because you do understand but find this does not match
reality), then please contact a demonstrator or the laboratory
leader about this."""
        
            tests.append((False,"import s.py", error_report))
            log.info("n == 0: Appending failed test for import")

            return tests,status
        else:
            raise RuntimeError,"A new bug has occured -- see logs for detail.\n"+\
            "In this case, the problem may originate from a py.test version newer than 2.1.2.\n"+\
            "We do a lot of tests to see whether a particular bug is a particular bug (see source for bug 1)\n"+\
            "and if any of the output changes significantly, this test will fail.\n\n"+\
            "The failed job should be the first one in the testing queue."

    #special case.
    bug_2_description="""March 2013. It seems that submissions containing non-ASCII characters
    which would usually result in an "SyntaxError: Non-ASCII character
    '\xff' in file..."  can cause problems in py.test 2.3.4, which
    fails (when called with the flags we use; running py.test without
    the "--resultlog=" flag set gives the correct error) with this
    behaviour:

      -  pytest_log contains the text in the pytest_log_bug2 variable (defined below).
      
      - pytest.stderr is an empty file          

      - pytest.stdout contains the text in the pytest_stdout_bug2 varaible (defined below).

    The detailed files are available in
    code/python/subtest/bugs/bug-archive-non-ascii-pytest2.3.4

    So py.test seems to be buggy and ONLY in combination with the
    --resultlog switch. Decativing this --resultlog, gives the right
    error message.

    We will try to catch this here and ask the user(=student) to make
    sure they can 'run' their file through the interpreter without
    getting an error message.
    
"""

    pytest_log_bug2 = """! /usr/local/lib/python2.7/dist-packages/_pytest/resultlog.py
 Traceback (most recent call last):
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 81, in wrap_session
     doit(config, session)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 112, in _main
     config.hook.pytest_collection(session=session)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 422, in __call__
     return self._docall(methods, kwargs)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 433, in _docall
     res = mc.execute()
   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 351, in execute
     res = method(**kwargs)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 116, in pytest_collection
     return session.perform_collect()
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 465, in perform_collect
     items = self._perform_collect(args, genitems)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 498, in _perform_collect
     self.items.extend(self.genitems(node))
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 643, in genitems
     node.ihook.pytest_collectreport(report=rep)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 157, in call_matching_hooks
     return hookmethod.pcall(plugins, **kwargs)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 426, in pcall
     return self._docall(methods, kwargs)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 433, in _docall
     res = mc.execute()
   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 351, in execute
     res = method(**kwargs)
   File "/usr/local/lib/python2.7/dist-packages/_pytest/resultlog.py", line 88, in pytest_collectreport
     longrepr = str(report.longrepr.reprcrash)
 AttributeError: CollectErrorRepr instance has no attribute 'reprcrash'"""

    pytest_stdout_bug2 = """============================= test session starts ==============================
platform linux2 -- Python 2.7.3 -- pytest-2.3.4
INTERNALERROR> Traceback (most recent call last):
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 81, in wrap_session
INTERNALERROR>     doit(config, session)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 112, in _main
INTERNALERROR>     config.hook.pytest_collection(session=session)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 422, in __call__
INTERNALERROR>     return self._docall(methods, kwargs)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 433, in _docall
INTERNALERROR>     res = mc.execute()
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 351, in execute
INTERNALERROR>     res = method(**kwargs)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 116, in pytest_collection
INTERNALERROR>     return session.perform_collect()
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 465, in perform_collect
INTERNALERROR>     items = self._perform_collect(args, genitems)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 498, in _perform_collect
INTERNALERROR>     self.items.extend(self.genitems(node))
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 643, in genitems
INTERNALERROR>     node.ihook.pytest_collectreport(report=rep)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/main.py", line 157, in call_matching_hooks
INTERNALERROR>     return hookmethod.pcall(plugins, **kwargs)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 426, in pcall
INTERNALERROR>     return self._docall(methods, kwargs)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 433, in _docall
INTERNALERROR>     res = mc.execute()
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/core.py", line 351, in execute
INTERNALERROR>     res = method(**kwargs)
INTERNALERROR>   File "/usr/local/lib/python2.7/dist-packages/_pytest/resultlog.py", line 88, in pytest_collectreport
INTERNALERROR>     longrepr = str(report.longrepr.reprcrash)
INTERNALERROR> AttributeError: CollectErrorRepr instance has no attribute 'reprcrash'

=========================== 1 error in 0.23 seconds ============================"""

    # Test for BUG 2.  The likely-fragile is in the function we call
    # here.
    if (looks_like_bug2(dirpath, log)):
        # When suspecting the bug, log it, inform the student (via the
        # returned tuple), and inform the admin (via email directly).

        log.info("Reached branch for suspected BUG 2")

        error_report = error_report_import_failed 

        admin_errorreport = """
Suspect BUG 2 in subtest:__init__.py (import of file [with non-ASCII
characters?     ] fails).

This arose in directory {0:s}.  The following error report has been
included in an email to the student.\n\n""".format(dirpath) + error_report

        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, 
                                                 conf.ModuleEmailAddress, 
                                                 admin_errorreport, 
                                                 "Error importing student submission", 
                                                 html=False)

        tests.append((False,"import s.py",error_report))
        return tests,status

    # otherwise carry on -- this is the normal case.
    i = 0
    while i<n:
        log.info("i={}, n={}, parsing line '{}'".format(i, n, lines[i]))
        
        if len(lines[i]) == 0:  
            raise ValueError,"Empty line [%d] in '%s' -- impossible" % (i,path)
        testname = lines[i][1:].strip()
        if lines[i][0] == '.': #passed
            tests.append((True,testname,None))
            i=i+1
        elif lines[i][0] == 'F': #failed        
            #Errors that have ocurred while executing any functions defined as 'def test_'
            #will be correctly reported in the pytest_log file. For example:
            #F 5NYr6E/test_tenfunc.py:test_log2
            #
            #If there is an error when the s.py file is imported, this will not be
            #explained in pytest_log (but in pytest.stdout). The corresponding location
            #of the error in pytest_log reads:
            #F _test-2009-09-23-23:00:04/test_lab1.py
            #
            #Note that in case 1, the failing function ('test_log2') is mentioned whereas
            #below that in case2, only the failing file is mentioned ('test_lab1').
            #Can use this to distinguish the cases:

            #Need to catch this case
            if lines[i].strip().endswith(".py"): #if this ends with .py, then the import has failed
                import_error= '\nThere was an error when importing your file:\n'\
                              +open(os.path.join(dirpath,'pytest.stdout')).read()
                              
                import_error += error_report_import_failed 

                              
                log.debug("Have identified an import error: import_error message='{}'"
                    .format(import_error))

            else:
                import_error="" #import_error = "Not an import error, lines[i]='%s'" % lines[i]

            i = i + 1
            errorreport = ""
            #Now normal parsing of the next (indented) lines:
            while lines[i][0] == " ":
                errorreport += lines[i][1:]
                i=i+1
                if i==n:
                    break
                if len(lines[i])==0:
                    raise ValueError,"Empty line [%d] in '%s' -- impossible" % (i,path)
            errorreport += import_error
            log.debug("Final error report for {} is '{}'".format(testname, errorreport))
            tests.append((False, testname, errorreport))

        else: # This line has length but does not start with '.' or
              # 'F'.  Should not happen, warn admin and student.
            admin_errorreport="""Error in parse_pytest_report.  We encountered a line in pytest_log
which begins neither with '.' nor 'F'.  This may be a bug.  The
directory in which this error arose is {0:s} and the contents of the
pytest_log file follow.""".format(dirpath)
            admin_errorreport += "\n\n"
            with open(path,'r') as fh:
                admin_errorreport += fh.read()

            enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress, admin_errorreport, "Error parsing pytest_log", html=False)

            error_report="""An error has occurred in parsing the log file pytest_log.  This may be
due to issues with your submission, or it may be because of a bug in
the testing system.  The laboratory leader has been informed.

Please ensure that you can run your file (either by pressing F5 in
IDLE, or running "python MYFILE.py") without getting any errors,
*BEFORE* submitting it.

If you are submitting C code, please ensure it compiles without
errors before submitting.

If the above makes no sense (either because you don't understand
it, or because you do understand but find this does not match
reality), then please contact a demonstrator or the laboratory
leader about this."""

            tests.append((False,"Error parsing pytest_log",error_report))
            return tests,status

    log.debug("leaving parse_pytest_report normally. Data: \ntests={}".format(tests))
    log.debug("status={}".format(status))
    

    return tests, status

def looks_like_bug2(dirpath, log):
    """Checks whether certain patterns exist in the files
    'dirpath/pytest_log' and 'dirpath/pytest_stdout' which look like
    signs of bug 2 (see comments above).  Returns True if so, False if
    not."""

    match_count = 0

    # 1 - read the files.
    with open(os.path.join(dirpath,conf.pytest_log),'r') as fh:
        pytest_log_lines = fh.readlines()
    with open(os.path.join(dirpath,conf.pytest_stdout),'r') as fh:
        pytest_stdout_lines = fh.readlines()

    # 2 - check pytest_log
    expressions = [r'^! /usr/local/lib/python2.7/dist-packages/_pytest/resultlog.py$',
                   r'.*File ".*resultlog.py.*line.*pytest_collectreport',
                   r'.*longrepr = str\(report\.longrepr\.reprcrash\).*',
                   r".*AttributeError: CollectErrorRepr instance has no attribute 'reprcrash'"]

    match_count += sum(map(lambda x: (1 if x != None else 0), [re.match(p,l) for l in pytest_log_lines for p in expressions]))

    # 3 - check pytest_stdout
    expressions = [r'^INTERNALERROR> Traceback \(most recent call last\):',
                   r'^INTERNALERROR>   File ".*resultlog.py", line .*, in pytest_collectreport',
                   r'^INTERNALERROR>     longrepr = str\(report.longrepr.reprcrash\)',
                   r"^INTERNALERROR> AttributeError: CollectErrorRepr instance has no attribute 'reprcrash'",
                   r"^=========================== 1 error in .* seconds ============================"]

    match_count += sum(map(lambda x: (1 if x != None else 0), [re.match(p,l) for l in pytest_stdout_lines for p in expressions]))

    # The "3" below is an arbitrary choice, increase it if this test
    # returns false positives.  Max value is currently 9 (max total
    # number of matches possible for pytest_log_lines and
    # pytest_stderr_lines).
    log.debug("looks_like_bug2: match_count = {}.".format(match_count))
    if(match_count > 3):
        return True
    else:
        return False


def summary_text(report_data):

    m=[]
    passed,failed,total = conf.pass_fail_total(report_data)
    m.append("Summary:  Passed %2d, Failed %2d" % (passed,failed))
    m.append("==============================")
    
    m.append("")
    m.append("Total mark for this assignment: {} / {} = {:.0f}%".format(
            passed, passed + failed, passed / float(passed + failed) * 100))
    m.append("")
        
    m.append("")
    m.append(pass_fail_overview(report_data))
    if failed > 0:
        m.append("Test failure report ")
        m.append("====================")
        m.append("")

        for passed, testname, error in [x for x in report_data if x[0]==False]:
            name = test_shortname(testname)
            m.append("%s" % name)
            m.append("-"*len(name))
            if conf.rst_format:     #switch to source code
                m.append("::")
                m.append("")
                m.append("  "+error.replace('\n','\n  ')) #indent block
            else:
                m.append(error)
            m.append("")
        
        
            
    return "\n".join(m)
    
    



def pass_fail_overview(report_data):
    m=[]
    m.append("Pass/fail overview")
    m.append("==================")
    m.append("")

    if conf.rst_format:
        sep = ' '
    else:
        sep = ':'
    
    if conf.rst_format:
        m.append("======== ======================")
    for passed, testname, error in report_data:
        if passed:
            line="ok     %s " % sep
        else:
            line="failed %s " % sep
            line += " %s" % test_shortname(testname)
        m.append(line)
    if conf.rst_format:
        m.append("======== ======================")
    m.append("")
    
    return "\n".join(m)

def overview_header():
    s = "Overview\n"
    s +="========\n"
    return s

def overview_item(report, comment=""):
    assert report['mark-max'] != 0.0, \
        "Need to mark_item_compile before preparing the overview."
    
    name = report['name']   
    if report['pass'] == True:
        resultstr = 'passed'
    elif report['pass'] == False:
        resultstr = 'failed'
    else:
        raise RuntimeError("Should be impossible: report['pass'] == None. \n{}".format(
            report))
            
    resultstr2 = "{:10}    -> {:3.0f}%".format(resultstr, 
        report['mark'] / float(report['mark-max'])*100)
    s = "{:40} : {:20} ; with weight {}".format(name, resultstr2, report['weight'])
    return s       


def overview_item_compile(report):

    log = report['lab-logger']
    name = report['name']
    mark, msg, results = ctestlib.assess_gcc_compilation2(name, log)
        
    assert report['pass'] is True, \
        "For compilation, this should always be True. Full report:\n\t{}".\
            format(pprint.pformat(report))
    
    assert report['mark-max'] != 0.0, \
        "Need to mark_item_compile before preparing the overview."

    nr_errors = report['nr_errors']
    nr_warnings = report['nr_warnings']
    resultstr = "{:2} Err,{:2} War -> {:3.0f}%".format(nr_errors, 
                                                      nr_warnings,
                                                      mark * 100)
      
    s = "{:40} : {:20} ; with weight {}".format(name, resultstr, report['weight'])
    return s       

def overview_item_pep8(report):
    
    name = report['name']   
    directory = report['studentlabdir']
    #logger = report['logger']
    assert report['mark-max'] != 0.0, \
        "Need to mark_item_compile before preparing the overview."

    mark, msg, results = tetepy.assess_pep8(directory, None)

    nr_errors = results['nr_errors']

    resultstr = "{:3} errors    -> {:3.0f}%".format(nr_errors, mark * 100)
  
    s = "{:40} : {:20} ; with weight {}".format(name, 
                                                resultstr, 
                                                report['weight'])
    return s


def pytest_stdout(report):
    path = os.path.join(report['studentlabdir'], conf.pytest_stdout)
    return open(path, 'r').read()


def feedback_header(report):
    m = []
    m.append("Test failure report ")
    m.append("====================")
    m.append("")
    return "\n".join(m)


def feedback_item(report):
    passed = report['pass'] 
    testname = report['name'] 
    error = report['raw-feedback']
    if passed:
        return None
    m = []        
    name = conf.test_shortname(testname)
    m.append("%s" % name)
    m.append("-"*len(name))
    if conf.rst_format:     #switch to source code
        m.append("::")
        m.append("")
        m.append("  "+error.replace('\n','\n  ')) #indent block
    else:
        m.append(error)
        m.append("")
    return "\n".join(m)    


def feedback_item_compile(report):
    log = report['lab-logger']
 
    name = report['name']
    mark, msg, results = ctestlib.assess_gcc_compilation2(name, log)
    
    m = []        
    m.append("%s" % name)
    m.append("-"*len(name))

    if conf.rst_format:     #switch to source code
        m.append("::")
        m.append("")
        m.append("  "+msg.replace('\n','\n  ')) #indent block
    else:
        m.append(msg)
        m.append("")
    return "\n".join(m)    


def feedback_item_pep8(report):
    log = report['lab-logger']
 
    name = report['name']
    directory = ['studentlabdir']
    mark, msg, results = tetepy.assess_pep8(directory, log)

    m = []     
    title = "Testing for PEP8 Compliance of whole file ({})".format(name)
    
    m.append("%s" % title)
    m.append("-"*len(title))

    if conf.rst_format:     #switch to source code
        m.append("::")
        m.append("")
        m.append("  "+msg.replace('\n','\n  ')) #indent block
    else:
        m.append(msg)
        m.append("")
    return "\n".join(m)
    

def mark_item(report):
    """ Given the report, return (mark, max-mark)."""
    if report['pass'] == True:
        report['mark'] = 1  
    else:
        report['mark'] = 0 
  
    report['mark-max'] = 1 
  
    return report['mark'], report['mark-max']


def mark_item_compile(report):
    """ Given the report, return (mark, max-mark)."""
    
    log = report['lab-logger'] 
        
    mark, msg, results = ctestlib.assess_gcc_compilation2(report['name'], log)
    
    report['mark'] = mark
    report['mark-max'] = 1.0
    report['nr_errors'] = results['nr_errors']
    report['nr_warnings'] = results['nr_warnings']

    return report['mark'], report['mark-max']


def mark_item_pep8(report):
    """ Given the report, return (mark, max-mark)."""
            
    mark, msg, results = tetepy.assess_pep8(report['name'])
    
    report['mark'] = mark
    report['mark-max'] = 1.0

    return report['mark'], report['mark-max']



def create_summary_text_and_marks(report_data, studentlabdir, logglobal):
    """
    Parameters
    ----------

      report_data : list of triplets
         Report data has the following structure: there is one triplet (i.e.
         a tuple with three entries) for every test_* function. In each triplet
         we have (A, B, C):
             A is a bool, and True if the test has passed and False if failed
             B is the name of the test, with the filename of the test*.py file
               (see example below)
             C is the stdout from running py.test.
        
      studentlabdir : str
         Path to directory in which files are.
         
      logglobal : logging.Logger
         global logger object
         
        
    Returns
    -------

       summary_text : str
          Major chunk of feedback email, comprising of 
          - overview of passed exercises and marks
          - total mark for assignment
          - more detailed feedback for each exercise
          
       passfailtotal : triplet of floats (A, B, C)
          
          - returns the obtained marks A out of the available C.
            B is the failed fraction. Historically, these were 
            tests and integer numbers, but we now also allow fractions,
            and could in principle normalise so that C = 100%.
            One of the three parameters is redundant - again for historical 
            reasons.
            
        
    Example
    -------

    Here is an example for report_data::
    
        [(True, 'test_training3_c.py::test_hello_world_compilation', None), 
         (False, 'test_training3_c.py::test_output_exit_code_is_zero', 
          "def test_output_exit_code_is_zero():\n        
          ct.attempt_compilation_and_execution(cache)\n    \n        
          #Did the program compile?\n>       
          assert cache['compilation-success'] == True\nE       
          assert False == True\n\ntest_training3_c.py:58: AssertionError\n"), 
          (False, 'test_training3_c.py::test_output_contains_hello_world', 
           "def test_output_contains_hello_world():\n    \n        
           # attempt to compile and execute code, store results in cache\n        
           ct.attempt_compilation_and_execution(cache)\n    \n        
           # Did the program compile?\n>       
           assert cache['compilation-success'] == True\nE       
           assert False == True\n\ntest_training3_c.py:70: AssertionError\n")]
    """
    
    
    r = report_data
    assert len(r) > 0, "Didn't get any data to summarise"
    
    # create local logger
    log = mylogger.attach_to_logfile(os.path.join(studentlabdir, 'log.txt'),
                                                  level=logging.DEBUG)
    

    # Extract name of file with tests    
    testfilename = r[0][1].split('::')[0]
    
    log.info("Processing {} tests from file {} in {}".format(
        len(r), testfilename, studentlabdir))

    # Data structure to complete as we parse the test results    
    reports = []
    
    # Gather what tests we need to analyse
    for line in r:
        d = {'name':None,               # Name of test_function 
                                        #   i.e. test_hello_world_compilation
             'summary-line':None,       # one-line summary of performance
             'feedback-item':None,      # more detailed feedback
             'mark':0.,                 # actual mark
             'mark-max': 0.,            # maximum mark available
             'pass':None}               # test passed? [not sure we need this]
            
        # store all the data we have
        try:
            d['name'] = line[1].split('::')[1]   # name of the test function
        except IndexError, msg:
            msg2 = "This Error means typically that the testing script"+\
                "has failed import the student data: \nreport-data = {}".format(report_data) + \
                "studentlabdir = {}\n\nOriginal={}".format(studentlabdir,
                msg) + "\nline = '{}'".format(line)
            logglobal.info(msg2)
            print(msg2)
            # common reasons are syntax errors or semantic errors that
            # are discovered / triggered when the system imports the file
            d['name'] = testfilename
            d['summary-line'] = "import failed"
    
        d['pass'] = line[0]
        d['raw-feedback'] = line[2]
        d['testfilename'] = testfilename
        d['studentlabdir'] = studentlabdir
        d['lab-logger'] = log

        # can analyise further, later
        reports.append(d)
            
    log.info("Found these tests: {}".format(
        [t['name'] for t in reports]))



    # Change Working directory to student lab test directory
    org_working_directory = os.getcwd()
    log.debug("store current cwd = {}".format(org_working_directory))
    # cd into student test lab directory
    os.chdir(studentlabdir)        
    log.debug("current now = {}".format(os.getcwd()))
        

    # Now analyse them one-by-one
    for report in reports:
     
        log.info("Working on {}".format(report['name']))
        
        
        # Have we been given special instructions what to do with this test?
        testfilenamepure = testfilename
        if testfilenamepure[0:5] == "test_":
            testfilenamepure = testfilenamepure[5:]
        if testfilenamepure[-3:] == '.py':
            testfilenamepure = testfilenamepure[:-3]
        
        log.info("report={}".format(report))
        log.info("testfilenamepure={}, testfilename={}".format(\
            testfilenamepure, testfilename))
            
        # if import s has failed, then 'testfilenamepure' may not be correct      
        if not testfilenamepure in conf.subtest_postprocessing: 
            log.warn("testfilenamepure = {} not known -> import fail?"
                .format(testfilenamepure))
            importfail = True
        else:
            importfail = False
                
        if not importfail:
            # are postprocessing files specified in the configuration  
            if report['name'] in conf.subtest_postprocessing[testfilenamepure]:
                the_dic = conf.subtest_postprocessing[testfilenamepure][report['name']]
                log.info("Testfile {}, found specialised test '{}' (not using default)"\
                    .format(testfilename, report['name']))
                # otherwise assume it is a standard python test (or parsing of stdout)        
            else:
                the_dic = conf.subtest_postprocessing[testfilenamepure]['default']
                log.info("Testfile {}, didn't find specialised test for {}, using default"\
                    .format(testfilename, report['name']))
        else:
                the_dic = conf.subtest_postprocessing['default-fallback']
            
        mark_item_ = the_dic['mark-item']
        overview_item_ = the_dic['overview-item']
        overview_header_ = the_dic['overview-header']
        feedback_header_ = the_dic['feedback-header']
        feedback_item_ = the_dic['feedback-item']
        weight = the_dic['weight']
        
        log.info("Using mark_item function:      {}".format(mark_item.__name__))        
        log.info("Using overview_item function:  {}".format(overview_item.__name__))        
        log.info("Using feedback_item function:  {}".format(feedback_item.__name__))        
        log.info("Using overview_header function:{}".format(overview_header.__name__))      
        log.info("Using feedback_header function:{}".format(feedback_header.__name__))        
        
        # store weight for this question
        report['weight'] = weight
     
        # process the submission
        report['mark'], report['mark-max'] = mark_item_(report)
        report['summary-line'] = overview_item_(report)        
        report['feedback-item'] = feedback_item_(report)

        # store key data in global log file for convenient post processing
        logglobal.info("Assessment summary: {}::{}::{}, mark {}/{}, weight={}"
            .format(studentlabdir, testfilename, 'summary', 
                    report['mark'], report['mark-max'], report['weight'] ))        

        
    # Compose message
    msg = []

    # Overview of pass / fail    
    msg.append(overview_header_())
    for report in reports:
        msg.append(report['summary-line']) 

    # Summary mark
    log.info("report={}".format(report))
    log.info("mark={}".format(report['mark']))
    points = sum([report['mark']*report['weight'] for report in reports])
    maxpoints = sum([report['mark-max']*report['weight'] for report in reports])

    logglobal.info("Assessment summary: {}::{}::{}, totalmark {}/{}={}%"
        .format(studentlabdir, testfilename, report['name'], 
        points, maxpoints, points / float(maxpoints) * 100))        


    # Create string showing the equation
    s = []
    for report in reports:
        w = report['weight']
        if w == 1:
            s.append("{}".format(report['mark']))
        else:
            s.append("{} * {}".format(w, report['mark']))
    computation_mark = " + ".join(s) 
    computation_mark += " = {}".format(points)
        
    msg.append("\n")
    msg.append("Total mark for this assignment: {} / {} = {:.0f}%.\n".format(
            points, maxpoints, points / float(maxpoints) * 100))
    msg.append("\n(Points computed as {})".format(computation_mark))
    msg.append("\n")
    
    # convert results into legacy format
    marks = (points, maxpoints - points, maxpoints)
    
    # more detailed feedback on failed tests
    if maxpoints - points != 0:
        msg.append(feedback_header_(report))
        for report in reports:
            if report['mark'] != report['mark-max']:
                msg.append(report['feedback-item'])
                               
                               
        if conf.include_pytest_stdout or conf.include_pprinted_report:
            msg.append("\n\n" + 70 * "#" + "\n\n")
            msg.append("Additional debugging details")
            msg.append("----------------------------")
            msg.append("\n")
            msg.append("The additional information below can usually be ignored")
            msg.append("but maybe useful to track down some bugs.")
            msg.append("\n")
            
        if conf.include_pytest_stdout:
            msg.append("Standard output from running py.test:\n")
            msg.append(pytest_stdout(report))
            msg.append("\n")
            
        if conf.include_pprinted_report:
            msg.append("Overview of meta data for this assignment:\n")
            
            # make reports more readable by getting rid of 'feedback-item'
            # and 'raw-feedback'
            
            for report in reports:
                report_slim = copy.copy(report)
                report_slim.pop('raw-feedback')
                report_slim.pop('feedback-item')
                report_slim.pop('lab-logger')
            
                msg.append("### Report '{}' ###".format(report_slim['name']))
                msg.append(pprint.pformat(report_slim, indent=4))
                msg.append("- - - " * 12)
            msg.append("\n")

        if conf.include_pytest_stdout or conf.include_pprinted_report:
            msg.append("\n\n" + 70 * "#" + "\n\n")
    
    # change back into original working directory
    os.chdir(org_working_directory)
    log.debug("back to original cwd = {}".format(os.getcwd()))
    return "\n".join(msg), marks


def test_shortname(longname):
    """returns 'test_powers' for given 'test/test_tenfunc.py:test_powers
    or test-2009-09-07-17:22:02/test_lab1.py:test_fall_time'"""

    p=re.compile(r"([+.0-9a-zA-Z_-]+)/test_([+.0-9a-zA-Z_-]+:)")

    m=p.search(longname)

    if m != None:
        return longname[m.span()[1]:]
    else:
        ##This happens if the name of the test-function is not displayed, because
        ##already importing the file to be tested fails.
        ##We just return the full path (with the advantage of assisting later debugging).
        #import sys
        #sys.stderr.write("Couldn't find shortname in '%s' (subtest/__init__.py/testshortname()\n)" % longname)
        #sys.stderr.write("Warning only, will return long name and proceed\n")
        return longname
    
    return longname 

