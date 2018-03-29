# This file is part of the TeTePy software
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


# Configuration file for TeTePy Test Suite.

import os.path 
import logging 
import textwrap 
import copy
import dateutil.parser
import mylogger

import post_test_analysis

log_level=logging.INFO
#log_level=logging.DEBUG

#get module code automatically from environment
try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"

Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()
ModulecodeSubjectLine = Modulecode

Year='20172018'

home = os.getenv('HOME')
if home == None:
        raise "Couldn't get environment variable HOME. Stop here"

Homedir = os.path.join(home,Year)
Maildir = os.path.join(Homedir,'mail')
Submissiondir = os.path.join(Homedir,'submissions')
Tempdir = os.path.join(Homedir,'tmp')
Lockdir = os.path.join(Homedir,'locks')

Studentlistdir = os.path.join(Homedir, 'studentlist')
Studentlistcsvfile = os.path.join(Studentlistdir,
                                      'nameemail.csv.' + Modulecode.lower())

# Logfile dealing with processing of incoming emails from students
Logfile = os.path.join(Homedir,'log/main.log')

# Can check this file periodically to check that services are running
pulsefile = os.path.join(Homedir,'log','pulse-process-emails.dat')

# where do we store the inbox -- good to stick to Linux convention
inbox = os.path.join('/var/mail',Modulecode.lower())



# file for temporary mail processing (do we need it?) 
tmpname = os.path.join(Homedir,'mail/_tmp')

# directory for html reports on submissions
HTMLreportdir = os.path.join(Homedir,'htmlreport')

# The email address to which students submit their files
ModuleEmailAddress = "tetepysubmission@example.org"

# List of email addresses that should receive admin emails with
# errors, forwarding of daemon-emails etc.
SysadminEmail = "tetepyadmin@example.org"
SysadminName = "TeTePy Admin"

# Acceptance of emails can be based on the domain where they come from
# (old system), or we provide an explicite list of students who are allowed
# to submit (new system, and more secure.)
Domain = "example.org"

# address for email delivery. Easiest is localhost, i.e. 127.0.0.1
smtp = '127.0.0.1'


# Specify assignments (here 'lab1', and for each assignment
# what files we expect, and which are mandatory or optional.)
#
# See more examples at end of file.



demo = {'demo.py':('mandatory',100)}

demo2 = {'demo2.py':('mandatory',100)}

# We need to summarise the individual assignments, in a dictionary
# with hardcoded name assignments:
#

assignments = {'demo': demo,
               'demo2': demo2}


# Deadline groups 

# Keys to this dictionary are the names of the deadline groups, which
# must match those in the file specified as Studentlistcsvfile.
# Values are dictionaries of assignments and their deadlines.
#
# Example which sets up three deadline groups:
# deadline_groups = {
#  'Campus1': {'demo': '20 Nov 2018 09:00', 'demo2': '27 Nov 2018 09:00'},
#  'Campus2': {'demo': '22 Nov 2018 09:00', 'demo2': '29 Nov 2018 09:00'},
#  'Campus3': {'demo': '23 Nov 2018 09:00', 'demo2': '30 Nov 2018 09:00'}}


def get_lab_deadline_groups():
    deadline_groups = {
	'Campus1': {'demo': '23 Oct 2015 16:00',
                'demo2': '30 Oct 2015 15:00'},
	'Campus2': {'demo': '23 Oct 2015 18:00',
                'demo2': '30 Oct 2015 18:00'}}

    # convert this clear text into datetime objects
    s = {}
    for group in deadline_groups:
        s[group] = {}
        for assignment in deadline_groups[group]:
            s[group][assignment] = dateutil.parser.parse(
                deadline_groups[group][assignment])

    return s

deadline_groups = get_lab_deadline_groups()



#
# Testing of code
#

# If an error occurs in at least one test, should we print the standard output as 
# captured by py.test? This includes anything printed to stdout in the function
# that failed, and can thus give extra debug information.
# 
# Recommended for testing of C code; and could be useful for Python testing            
include_pytest_stdout = True

# If an error occurs in at least one test, should we print the meta data 
# (the 'report' dictionary) about the test? This looks rather cryptic 
# but is useful for C-programming (it gives clues if the execution had to be 
# terminated, or a segfault used, etc.)
include_pprinted_report = False
            
            
subtest_base = os.path.join(Homedir,'testingcode')
subtest_testcodedir = os.path.join(subtest_base,Modulecode.lower()) 
subtest_queue = os.path.join(subtest_base,'queue')
subtest_manual = os.path.join(subtest_base,'manual')
subtest_locks  = os.path.join(subtest_base,'locks')
subtest_logfile = os.path.join(Homedir,'log','subtest.log')
subtest_pulsefile =  os.path.join(Homedir,'log','pulse-process-subtest.dat')
subtest_maxseconds = 60 # maximum time py.test run may take 

# The files that contain the tests
subtest_tests = {'demo': 'test_demo.py',
                 'demo2': 'test_demo2.py'}


# We now define more detailed post-processing functions 
# FOR EACH TESTFUNCTION in each test file.
#
# The set of postprocessing, reporting and marking tools that should be
# just fine for each test-function used in 
# - python teaching
# - python based tests that analyse stdout from executed C programs
default_postprocessing_python = {'overview-header' : post_test_analysis.overview_header,
                                 'overview-item' : post_test_analysis.overview_item,
                                 'feedback-header' : post_test_analysis.feedback_header,
                                 'feedback-item' : post_test_analysis.feedback_item,
                                 'mark-item' : post_test_analysis.mark_item,
                                 'weight' : 1  # the weight of this question relative to other questions
                                 }

# slight variation for analysing the compilation of code, based on the python defaults
default_postprocessing_compilation = copy.copy(default_postprocessing_python)
# then modify cor analysing output from attempting to compile code with gcc:    
default_postprocessing_compilation['overview-item'] = post_test_analysis.overview_item_compile
default_postprocessing_compilation['feedback-item'] = post_test_analysis.feedback_item_compile
default_postprocessing_compilation['mark-item'] = post_test_analysis.mark_item_compile
default_postprocessing_compilation['weight'] = 5

# slight variation for analysing the pep8 checks
default_postprocessing_pep8 = copy.deepcopy(default_postprocessing_python)
# then modify cor analysing output from attempting to compile code with gcc:    
default_postprocessing_pep8['overview-item'] = post_test_analysis.overview_item_pep8
default_postprocessing_pep8['feedback-item'] = post_test_analysis.feedback_item_pep8
default_postprocessing_pep8['mark-item'] = post_test_analysis.mark_item_pep8
default_postprocessing_pep8['weight'] = 1


# Eventually, we need a set of postprocessing function for every test in each assignment:
#
# Do this automatically first (populate with template), then allow use
# to override.
subtest_postprocessing = {}
# populate subtest_postprocessing automatically with default values

for test in subtest_tests:  # this is training1, training2, ...
    if test not in subtest_postprocessing:
        subtest_postprocessing[test] = \
            {'default': default_postprocessing_python,
             'test_pep8': default_postprocessing_pep8}


# Add a default testing file -- this will be used if we can't find 
# the right filename in the index. Needed when an import error occurs
subtest_postprocessing['default-fallback'] = default_postprocessing_python

## Now override with specific entries where necessary
#subtest_postprocessing['training1']['test_pep8']['weight'] = 0.5
#subtest_postprocessing['training2']['test_pep8']['weight'] = 0.75
#subtest_postprocessing['lab2']['test_pep8']['weight'] = 0.75
#geometric_mean = copy.copy(default_postprocessing_python)
#geometric_mean['weight'] = 2


# The following should pass if we have testing activated.
# It cannoct be exhaustive (because we don't know the names of the
# test_functions within the test files yet), but if this fails, then 
# the testing will fail later.
for assignment in assignments:
    assert assignment in subtest_postprocessing

# ##################################################################
#
# Most of the following settings can be ignored
#

# Generic functions needed to read testing output. Safe to
# leave this set as default.
read_status = post_test_analysis.read_status
parse_pytest_report = post_test_analysis.parse_pytest_report
pass_fail_total = post_test_analysis.pass_fail_total
create_summary_text_and_marks = \
    post_test_analysis.create_summary_text_and_marks
test_shortname = post_test_analysis.test_shortname


# Variables for post-test analysis scripts to use.
statusfilename = 'status.txt'
pytest_stdout='pytest.stdout'
pytest_stderr='pytest.stderr'
pytest_log='pytest_log'


#The following options do not affect behaviour of the main testing system.
#However, if we include the stdout of the py.test process in the response
#email, then the following options matter: 
#    - capture=no   means to show output from print commands from the user
#      programme
#      
#      
#    - showlocals shows the local variables in the failing function.
#    
#    - verbose gives more detailed, for example shows one line of pass/fail
#       feedback for every test function (otherwise just  '.' is shown)
       
pytest_additional_arguments = "--showlocals --capture=no --verbose"


# Currently, all emails produced are plain text. It should be too hard to
# produce rst instead of just txt, and this would allow automatic conversion
# to html, say. Unfinished, so switched off by default (but partly implemented)
rst_format = False

# Log file for mark reporting errors, warning etc.
report_marks_logfile = os.path.join(Homedir,'log/report_marks.log')

# Usernames to not include in mark statistics etc.
unassessed_usernames = ['FETCHMAIL-DAEMON',
                        'MAILER-DAEMON']

# Defines the directory where outgoing emails are queued.
outgoingmail_queue = os.path.join(Homedir,'outgoingmail','queue')
outgoingmail_locks = os.path.join(Homedir,'outgoingmail','locks')
outgoingmail_logfile =  os.path.join(Homedir,'log','outgoingmail.log')
outgoingmail_processed = os.path.join(outgoingmail_queue,'processed')
outgoingmail_pulsefile = os.path.join(Homedir,'log','pulse-process-outgoingmail.dat')

# If something is in the outgoing mail queue, which cannot be parsed
# as a valid email message, it will end up in the following location.
outgoingmail_rejected = os.path.join(outgoingmail_queue,'rejected')

# If the SMTP server does not accept our connection attempts
# "smtp_error_threshold" times consecutively, the system will try to
# send (i.e. enqueue) a warning message to the administrator.  Repeat
# messages will then be generated every "smtp_error_repeat" hours
# until the server accepts the connection attempt.  The system uses
# "smtp_error_file" to record the timestamps required for this
# functionality.
smtp_error_threshold = 5
smtp_error_repeat = 24
smtp_error_file = os.path.join(outgoingmail_queue,'tmp','smtp_error.dat')

#if the next line is set to True, search in Studentlistcsvfile for the emails (
#first column).
#if email of submission is listed there, accept. Otherwise reject.
allow_only_emails_given_in_list=True
#if allow_only_emails_given_in_list =False, use domains and common
#sense checks on emailaddresses that are acceptable.

# time to sleep between subsequent runs (each parsing the inbox)
sleeptime = 0.1

sysadminmailfolder = 'sysadmin'

# Some text snippets to be send back to students in particular error
# situations:
TXT_Domain = """Only emails that are sent from the """+Domain+""" domain
will be accepted. (The reason being that we cannot associate external
email addresses to real names.)

This submission will be ignored.

Please re-send your email from your """+Domain+""" account.

(You can use Webmail for this.)
"""

TXT_address = """Your email address is not known to the submission
system. This means that your submission cannot be accepted.

*** Please ensure that you only send emails to this address
*** from your University account.

*** Work submitted from personal (Gmail, Hotmail, etc) accounts 
*** will not be accepted.

If you are enrolled to this course, and are seeing this message 
despite having sent work from your University email account,
please drop an email to %s (%s), 
please make sure you provide the following information: 
Surname, Forname(s), University email, Student ID number.""" % (SysadminName, SysadminEmail)


sent_data_base = os.path.join(Homedir,'log','error-sents-shelve')

# Helper string for error messages
valid_assignments = ""
mykeys = assignments.keys()
mykeys.sort()
for key in mykeys:
    valid_assignments += "\t"+key +"\n"

TXT_Submission = """The subject line of your email could not be parsed by the system.

Please use only one of the following tokens in the subject line to
state for which assignment you wish to submit files:

"""+valid_assignments+"""

This submission will be ignored.

Please re-send your email with a proper subject line.

""" + textwrap.fill("""
If you think your subject line is well chosen, then please inform
%s (%s).
You may have found a bug.\n""" % (SysadminName, SysadminEmail)



disclaimer = textwrap.fill("""This message has been generated automatically. Should you feel that
you observe a malfunction of the system, or if you wish to speak to a
human, please contact %s (%s).\n""" % (SysadminName, SysadminEmail))


if __name__ == "__main__":
    import pprint
    for name in sorted(dir()):
        print("{} = {}".format(name, pprint.pformat(eval(name))))


    for testfile in subtest_postprocessing:
        print "Testfile = ", testfile
        for test in subtest_postprocessing[testfile]:
            print "\ttest = ", test
            if testfile != 'default-fallback':
                for item in subtest_postprocessing[testfile][test]:
                    print "\t\t item={}, value = {}".format(item,subtest_postprocessing[testfile][test][item])


    #for datetime.weekday() -> int
    weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


    s = deadline_groups
    for groupname in s:
        print("Deadline group {}:".format(groupname))
        for labname in sorted(s[groupname].keys()):
            print "%s -> %s %s" % (labname,
                                   weekdays[s[groupname][labname].weekday()],
                                   s[groupname][labname])



# Safety check
assert os.path.exists(inbox), "Inbox file {} does not exist".format(inbox)

