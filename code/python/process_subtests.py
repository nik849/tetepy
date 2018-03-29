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

import os, logging, re, time, errno

from lab_helpers import lock_semaphore, unlock_semaphore
from lab_helpers import PyTestException

live = True

import mylogger
import subtest
import process_emails
import enqueue_outgoing_mails
import post_test_analysis

try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()


conf = __import__('config_' + Modulecode.lower())


def startup(log_level=logging.INFO):
    log_global = mylogger.attach_to_logfile( conf.subtest_logfile, level = log_level )
    process_emails.log_global=log_global #let functions in that module use the same logger
    enqueue_outgoing_mails.log_global=log_global
    enqueue_outgoing_mails.conf=conf
    post_test_analysis.conf=conf

    for dirname in (conf.subtest_testcodedir,conf.subtest_queue,
                    conf.subtest_manual,
                    os.path.split(conf.subtest_logfile)[0]):
        try:
            os.makedirs(dirname)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise
        except:
            log_global.critical("Unexpected error making directory {0}".format(dirname))
            raise

    log_global.debug(40*"=")
    log_global.debug("Starting program up, module={}".format(Modulecode))
    log_global.debug("Configfile = {}".format(conf.__file__))
    log_global.debug(40*"=")
    log_global.debug("============= Starting ===========")

    log_global.debug("Checking testing scripts are all in place:")
    #Check that testing codes are available
    for labname in conf.subtest_tests.keys():
        testfilename = conf.subtest_tests[labname]
        testfilepath = os.path.join(conf.subtest_testcodedir,labname,testfilename)
        log_global.debug("Checking labname={}, looking for {} at {}".format(
            labname, testfilename, testfilepath))
        assert os.path.exists(testfilepath), "Test file '%s' for submission '%s' is missing" \
               % (testfilepath,labname)

    # make sure PYTHONPATH is set to new modules and packages, such as 
    # ctestlib
    try:
        import tetepy
    except ImportError, msg0:
        msg = "We can't import 'tetepy'. \n\nIt shoud be installed via\n" + \
            "sudo sh ~/bin/install-python-libs.sh\n" +\
            "Original error: " + str(msg0)
        print(msg)
        log_global.error(msg)
        raise ImportError(msg)

    try:
        import ctestlib
    except ImportError, msg0:
        msg = "We can't import 'ctestlib'. \n\nIt shoud be installed via\n" + \
            "sudo sh ~/bin/install-python-libs.sh\n" +\
            "Original error: " + str(msg0)
        print(msg)
        log_global.error(msg)
        raise ImportError(msg)

    return log_global


def read_queue():
    def open_and_evaluate(filename):
        return eval(open(filename,'r').read())

    entryfiles = filter(lambda x: x[0:1] == "s", os.listdir(conf.subtest_queue))

    entryfilepaths = map(lambda x : os.path.join(conf.subtest_queue,x), entryfiles)

    entries = map(open_and_evaluate,entryfilepaths)

    return entries


def subtestqueue_pop(filename):
    filepath = os.path.join(conf.subtest_queue,filename)
    processed_directory=os.path.join(conf.subtest_queue,'processed')
    if not os.path.exists(processed_directory):
        log_global.info("Directory for processed jobs does not exist (%s), will create it now." % processed_directory)
        os.mkdir(processed_directory)
    filepath = os.path.join(conf.subtest_queue,filename)
    os.rename(filepath,os.path.join(processed_directory,filename))
    log_global.info("Remove '%s' from queue" % filename)


def find_memory_error(dir):
    """By reading the files pytest.stdout and pytest.stderr in the
    directory dir, this routine attempts to discover memory
    errors that arose during testing, returning True if at least one
    is found, and False otherwise.  It assumes that MemoryErrors will
    be reported in those files as lines starting with 'E' followed by
    some whitespace and the word 'MemoryError'"""

    memory_error = False
    files_to_check = ["pytest.stdout","pytest.stderr"]
    paths_to_check = [os.path.join(dir, filename) for filename in files_to_check]
    regexp = r"^E\s+MemoryError"

    for f in paths_to_check:

        with open(f,'r') as fh:
            lines = fh.readlines()

        for line in lines:
            if(re.match(regexp, line)):
                memory_error = True

    return memory_error


def process_one_subtest(job):
    student_lab_dir = job['student_lab_dir']
    testcodefile = conf.subtest_tests[job['assignment']]
    testcodepath = os.path.join(conf.subtest_testcodedir,
                                job['assignment'], testcodefile)

    all_submitted_files = conf.assignments[job['assignment']].keys()
    all_submitted_filepaths=[ os.path.join(student_lab_dir, fn) \
        for fn in all_submitted_files]

    submitted_filepath = None  # stop copying files to s.py

    log_global.info("Run py.test in %s " % student_lab_dir)

    try:
        if False:
            log_global.debug("Will run run_pytest (not constrained)")
            log_global.warn("Will run run_pytest (not constrained) -- not secure")  # student code could 
                                                                                    # damage files etc
            test_run_dir=subtest.run_pytest(submitted_filepath,testcodepath,
                                            rundirectorypath=student_lab_dir,
                                            jobfilepath=job['qfilepath'],
                                            maxseconds=conf.subtest_maxseconds,
                                            log_global=log_global)
        else:
            log_global.debug("Will run run_pytest_constrained")
            test_run_dir=subtest.run_pytest_constrained(submitted_filepath,testcodepath,
                                                        rundirectorypath=student_lab_dir,
                                                        other_submitted_filepaths=all_submitted_filepaths,
                                                        jobfilepath=job['qfilepath'],
                                                        maxseconds=conf.subtest_maxseconds,
                                                        log_global=log_global,
                                                        pytest_args=conf.pytest_additional_arguments)

    except PyTestException,msg:
        log_global.exception("pytest failed: %s" % msg)
        log_global.error("possible cause: error in test_*.py code?")
        ins,outs = os.popen4('tail -n 100 '+conf.subtest_logfile)
        text = outs.read()+'\n'+'Error message is:\n'+str(msg)
        subject = "Urgent: Malfunction in %s at %s (pytest reports problem)" % (conf.ModulecodeSubjectLine,time.asctime())
        enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress,text, subject)
        log_global.info("Emailed sysadmin (%s)" % conf.SysadminEmail)
        raise PyTestException,msg


    #always pointing to last submission
    shortcutname = os.path.join(student_lab_dir,'_test')
    if os.path.exists(shortcutname):
        os.remove(shortcutname)
    os.symlink(test_run_dir,shortcutname)

    #post-process and create email
    report,status=conf.parse_pytest_report(test_run_dir, log_global)
    if status == False:
        # Testing did not terminate.  Warn the student by email.
        # Separately email admin (below).
        log_global.info("Code didn't terminate (%s,%s,%s)" % (job['qfilename'],testcodefile,str(all_submitted_files)))
        subject = "[%s] %s testing failed (%s)" % (conf.ModulecodeSubjectLine.upper(),job['assignment'], time.asctime())
        text = "Dear %s,\n\nthe code you submitted did not terminate within\n" % job['real_name'] +\
               "the given time limit of %d seconds.\n\n" % (conf.subtest_maxseconds)+\
               """Possible reasons for this could be:

* you are doing a calculation that takes a long time

* your program is waiting for user input (using functions such as
  input() or raw_input())

* your program is caught in an infinite loop

Try to resolve this, so that all your functions return
swiftly (if called with reasonable parameters).

Please contact a demonstrator/lecturer if you cannot determine the
reason for non-termination of your code when being tested.

This submission attempt is not a valid submission -- please
improve code and resubmit.



More detailed analysis
----------------------

Below, we provide the outcome (ok/failed) of those tests that have been run
and terminated. The problem of non-termination is likely to be with the next
test to be run.

""" +post_test_analysis.summary_text(report)+\
               """\n\nAsk a demonstrator for help if this does not make sense to you.\n"""
        enqueue_outgoing_mails.send_text_message( job['email'], conf.ModuleEmailAddress,
                                          text, subject)

        admtext = """Unterminated code detected in job id {0:d}
(student lab directory was {1:s}).

Student {2:s} ({3:s}) was sent the following email.

""".format(job['id'], student_lab_dir, job['real_name'], job['login'])

        admtext = admtext + text
        admsubject = subject + " (" + job['login'] + " " + job['real_name'] + ")"

        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress,
                                          admtext, admsubject)
        log_global.info("Emailed administrator to warn of nonterminated code.")

    elif (find_memory_error(shortcutname)):
        # Terminated well with at least one MemoryError, warn student.
        log_global.info("Terminated with MemoryError %s" % (str(post_test_analysis.pass_fail_total(report))))

        subject = "[%s] %s job %d testing completed (%s)" % (conf.ModulecodeSubjectLine.upper(),job['assignment'],job['id'], time.asctime())
        text = "Dear %s,\n\ntesting of your submitted code has been completed,\n"  % job['real_name']
        text = text + "but we encountered at least one MemoryError during testing,\n"
        text = text + "which is a likely sign that something went wrong.\n\n"
        text = text + "Please ask a demonstrator or laboratory leader if you\n"
        text = text + "do not understand, feel that this is incorrect, or\n"
        text = text + "need assistance:\n\n\n"
        emailbody = text+post_test_analysis.summary_text(report)
        log_global.info("Sending email to %s, subject '%s'" % (job['email'],subject))
        enqueue_outgoing_mails.send_text_message( job['email'], conf.ModuleEmailAddress,
                                          emailbody, subject)

        admtext = """MemoryError detected in job id {0:d}
(student lab directory was {1:s}).

Student {2:s} ({3:s}) was sent the following email.

""".format(job['id'], student_lab_dir, job['real_name'], job['login'])

        admtext = admtext + emailbody
        admsubject = subject + " (" + job['login'] + " " + job['real_name'] + ")"

        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress,
                                          admtext, admsubject)
        log_global.info("Emailed administrator to warn of MemoryError in code.")

        #collect "pass/fail/total; datetime; id" data for assignment

        f=open(os.path.join(student_lab_dir,"_test_results.txt"),'a')
        f.write(str(conf.pass_fail_total(report))+';'+job['time']+';'+str(job['id'])+"\n")
        f.close()

        log_global.debug("Writing to _test_resuls.txt in %s:" % student_lab_dir)
        log_global.debug("\n"+str(conf.pass_fail_total(report))+';'+job['time']+';'+str(job['id'])+"\n")

    else:
        #
        # testing terminated well
        #
        log_global.info("Terminated well %s" % (str(conf.pass_fail_total(report))))

        subject = "[%s] %s job %d testing completed (%s)" % (conf.ModulecodeSubjectLine.upper(),job['assignment'],job['id'], time.asctime())
        text = "Dear %s,\n\ntesting of your submitted code has been completed:\n\n\n" % job['real_name']

        # The next function goes through the report 
        summary_text, passtotalfail = \
            conf.create_summary_text_and_marks(report,
                                               test_run_dir,
                                               log_global)

        emailbody = text + summary_text

        log_global.info("Sending email to %s, subject '%s'" % (job['email'],subject))
        enqueue_outgoing_mails.send_text_message( job['email'], conf.ModuleEmailAddress,
                                          emailbody, subject)

        # 
        #collect "pass/fail/total; datetime; id" data for assignment
        #
        f = open(os.path.join(student_lab_dir,"_test_results.txt"),'a')


        f.write(str(passtotalfail)+';'+job['time']+';'+str(job['id'])+"\n")
        f.close()

        log_global.debug("Writing to _test_resuls.txt in %s:" % student_lab_dir)
        log_global.debug("\n"+str(conf.pass_fail_total(report))+';'+job['time']+';'+str(job['id'])+"\n")



    subtestqueue_pop(job['qfilename'])


def process_queue():

    jobs = read_queue()

    if len(jobs)==0:
        log_global.info("Queue empty, quitting")
    else:
        log_global.info("Found %d job(s) (%s)" % (len(jobs),[job['id'] for job in jobs]))

    for job in jobs:
        log_global.info("Processing %s" % (job['qfilename']))
        process_one_subtest(job)


if __name__=="__main__":
    #if live, wait a bit so that emails can be processed and put into testing queue
    # before we start going through the testing queue.
    if live:
        if Modulecode == 'TEST':  # Make testing faster
            wait_time = 0;
        else:
            wait_time = 5 #in seconds
        time.sleep(wait_time)

    global log_global
    log_global = startup(log_level=conf.log_level)
    lock = lock_semaphore(conf.subtest_locks)

    if lock == False:
        log_global.info("Other process running, quitting")
    else: #all well

        log_global.debug("About to read queue")

        if live:
            try:
                process_queue()
                unlock_semaphore(lock)
            except:
                log_global.exception("Something went wrong (caught globally)")

                log_global.critical("Preparing email to sysadmin (%s)" % repr(conf.SysadminEmail))
                ins,outs = os.popen4('tail -n 50 '+conf.subtest_logfile)
                text = outs.read()
                subject = "URGENT: Malfunction in subtest %s at %s !!!" % (conf.ModulecodeSubjectLine,time.asctime())
                enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress,text, subject)
                log_global.info("Leaving now (not removing lockfile).")
                raise

        else:
            process_queue()
            unlock_semaphore(lock)

    import datetime,time
    f=open(conf.subtest_pulsefile,'w')
    data = {'now-secs':time.time(),'now-ascii':time.ctime(),'module':conf.ModulecodeSubjectLine,
            'what':"process-subtest"}
    f.write("%s" % repr(data))
    f.close()
    log_global.debug("About to leave, updated pulse.")
