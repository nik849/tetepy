#!/usr/bin/env python
#
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

import datetime, dateutil.parser, errno, os, os.path, re, textwrap, time
import enqueue_outgoing_mails

try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()

conf = __import__('config_' + Modulecode.lower())

import csvio, mylogger, process_emails

def check_student_groups(students, groups, email_admin=True):
    """Given the dictionary 'students', {'stud1@domain1':('stud1
    name','stud1_group'), ...}, and the list 'groups', checks that the
    group assigned to each student can be found in 'groups'.  If this
    is not the case the error is logged and, by default, the
    administrator is emailed a warning.  Returns a new students
    dictionary which is the input students dictionary, less any
    assigned to invalid groups, and a list of those students that were
    removed."""

    output_students = {}
    ignored_students = []

    for stud_email in students:
        (stud_name, stud_group) = students[stud_email]
        if stud_group not in groups:
            ignored_students.append("{0} ({1}) (group: {2})".format(stud_name, stud_email, stud_group))
            log_global.error("Student '{0}' ({1}) assigned group '{2}',"
                             " which is not in config file '{3}'.".format
                             (stud_name, stud_email, stud_group, 'config_' + Modulecode.lower()))
            if email_admin:
                subject = ("WARNING: {0}: student assigned to invalid group {1}".format(conf.ModulecodeSubjectLine,stud_group))
                text = ("The student {0} ({1}) is assigned to deadline group {2},"
                " which was not found in the configuration file {3}.  Marks for"
                " this student will not be recorded.".format(stud_name, stud_email, stud_group, 'config_' + Modulecode.lower()))
                text = textwrap.fill(text)
                enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress, text, subject)
        else:
            output_students[stud_email] = students[stud_email]

    return (output_students, ignored_students)

def gather_mark_data(student):
    """Given the student's login id as 'student', returns a dictionary
    of results for the given student, so that:
    marks['assignmentName'] = [fractionCorrect, dateOfSubmission] 
    where the fraction correct is calculated using the first line of the
    _test_results file only."""

    if(student.count('@') > 0):
        stud_dir = os.path.join(conf.Submissiondir, student.split('@')[0])
    else:
        stud_dir = os.path.join(conf.Submissiondir, student)

    try:
        labs = os.listdir(stud_dir)
    except OSError,e:
        if e.errno == errno.ENOENT: # No such file or directory.
            log_global.info("Student {0} has no student directory {1}.".format(student, stud_dir))
            return {} # Most likely, the student has not yet submitted.

    marks = {}
    for lab in labs:
        resultsfilename = os.path.join(stud_dir,lab,'_test_results.txt')
        if os.path.exists(resultsfilename):
            firstline = open(resultsfilename,'r').readlines()[0]
            # first line is first submission
            # convert score into list: [passed,failed,total]
            score = map(int,firstline.split(';')[0][1:-1].split(','))
            date = dateutil.parser.parse(firstline.split(';')[1])

            # sanity check:
            passed, failed, total = score
            assert passed+failed == total

            marks[lab]=[passed,total,date]
        else:
            log_global.info("Results file {0} does not exist.".format(resultsfilename))

    return marks

def remove_unassessed_submissions(mark_data, to_remove):
    """Given the dictionary mark_data and the list to_remove, returns
    the same dictionary less any entries whose key appears in
    to_remove."""
    for key in mark_data.keys():
        if key in to_remove:
            mark_data.pop(key)
    return mark_data


def find_max_activities(students, groups, activity_regex):
    """Given the student and group dictionaries, returns a dictionary
    of student IDs and the number of activities that match
    activity_regex, whose deadlines have passed (i.e. the number of
    activities we expect them to have completed)."""

    max_activities = {}
    for stud in students.keys():
        stud_activities = 0
        deadlines = groups[students[stud][1]]
        for activity in deadlines.keys():
            if re.match(activity_regex, activity):
                # We are counting this kind of activity.
                this_deadline = dateutil.parser.parse(deadlines[activity])
                now = datetime.datetime.now()
                if now > this_deadline:
                    # Deadline passed
                    stud_activities += 1

        max_activities[stud] = stud_activities

    return max_activities
                

def find_late_submissions(mark_data, students, groups):
    """Finds submissions that are dated later than the deadline."""
    late_submissions = {}

    studs = mark_data.keys()

    for stud in studs:
        stud_assigned_group = students[stud][1]
        stud_deadlines = groups[stud_assigned_group]

        for activity in stud_deadlines.keys():
            activity_deadline = dateutil.parser.parse(stud_deadlines[activity])
            try:
                submitted_date = mark_data[stud][activity][2]
            except KeyError:
                submitted_date = None
                print '#Key Error'
                continue
            if submitted_date > activity_deadline:
                if not late_submissions.has_key(stud):
                    late_submissions[stud] = {}
                late_submissions[stud][activity] = [submitted_date, activity_deadline, submitted_date - activity_deadline]
                    
    return late_submissions

def print_result_report(results, max_labs, activity_regex):
    print("Reporting on {0} for activities matching {1}\n".format(time.asctime(),activity_regex))
    print("Total number of students: {0}".format(len(results)))
    print("Average mark (across expected submissions): {0:.1f}%".format(sum([r[0] for r in results.values()])/float(max_labs)*100.))
    print("Average mark (across present submissions): {0:.1f}%".format(sum([r[1] for r in results.values()])/float(len(results))*100.))

    for r in sorted(results.keys()):
        print("{0:10s}: {1:5.1f}%, {2:5.1f}%".format(r,results[r][0]*100,results[r][1]*100))

def print_result_report(students, groups, mark_Data, stud_max_activities, 
                        late_submissions, ignored_students, activity_regex, 
                        out_filename):

    table = []
    for student in sorted(students.keys()):
        row = []

        student_name = students[student][0]
        student_group = students[student][1]

        if late_submissions.has_key(student):
            student_lates = late_submissions[student]
        else:
            student_lates = {}

        marks = [0.]*len(groups[student_group].keys())
        for i,lab in enumerate(groups[student_group].keys()):
            if lab in mark_data[student]:
                if lab not in student_lates.keys():
                    marks[i] = float(mark_data[student][lab][0])/mark_data[student][lab][1]
                else:
                    marks[i] = 0.
            else:
                marks[i] = 0.

        if len(student_lates) > 0:
            late_text = 'LATE: '
            for activity in student_lates:
                late_text += activity + ' (by: ' + str(student_lates[activity][2]) + ') '

            row = [student,student_name,student_group] + marks + [late_text]
        else:
            row = [student,student_name,student_group] + marks 

        print row
        table.append(row)


    f=open(out_filename, 'w')
    for row in table:
        f.write(",".join(map(str,row))+'\n')
    f.close()
    

if __name__ == "__main__":
    # Set up logging
    log_global = mylogger.attach_to_logfile(conf.report_marks_logfile, level = conf.log_level)
    process_emails.log_global=log_global #let functions in that module use the same logger
    log_global.info("report_marks.py starting up.")

    # Read student list, returns dictionary:
    # {'stud1@domain1':('stud1 name','stud1_group'), ...}
    students = csvio.readcsv_group(conf.Studentlistcsvfile)

    # Groups defined in config file.  Structure is a dictionary:
    # {'group1': {'lab3': '20 Nov 2009 09:00', 'lab4': '27 Nov 2009 09:00'},
    #  'group2': {'lab3': '22 Nov 2009 09:00', 'lab4': '29 Nov 2009 09:00'}}
    groups = conf.deadline_groups

    # Email admin if students are found assigned to deadline groups
    # that are not defined in the config.  ignored_students lists
    # those that had invalid groups and were removed.
    (students, ignored_students) = check_student_groups(students, groups.keys())

    # Populate the mark data so that
    # mark_data = {'stud1@domain': {'lab1': [fractionalScore, submissionDateTime], ...}, ...}
    mark_data={}
    for student in students:
        mark_data[student] = gather_mark_data(student)

    # Stop e.g. demonstrators' submissions affecting statistics.
    mark_data = remove_unassessed_submissions(mark_data, conf.unassessed_usernames)

    # Count max activities for each student.
    activity_regex = r'^training.*'
    stud_max_activities = find_max_activities(students, groups, activity_regex)

    # Find out if any were late.
    late_submissions = find_late_submissions(mark_data, students, groups)

    # Print to screen and file
    print_result_report(students, groups, mark_data, stud_max_activities, 
                        late_submissions, ignored_students, activity_regex, 
                        'tmp-labmarks.csv')
