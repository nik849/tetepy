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

import os
import sys

if len( sys.argv ) != 2:
    print "Provide path to submission log file as command line argument, please"
    sys.exit(1)

logfile = sys.argv[1]


def scan_log_file(logfile):
    """Returns list of tuples with jobs that were injected to testing queue.

    Each tuple contains (jobnumber, datetime, user, assignmentname)
    """

    f = open(logfile)

    submissions = []

    found_successful_test = False
    job = user = datetime = assignment = passed = failed = total = None

    for line in f:
        if found_successful_test:
            if 'Sending' in line:
                found_successful_test = False
                user = line.split('Sending email to ')[1].split(',')[0]
                assignment = line.split(' job')[0].split()[-1]
                job = int(line.split('job ')[1].split()[0])
                submissions.append( (job, datetime, user, assignment, passed, failed))
                job = user = datetime = assignment = passed = failed = total = None

        if 'Terminated well' in line:
            found_successful_test = True
            bits = line.strip().split("Terminated well (")[1].split(',')
            passed, failed, total = map(int, bits[0:2]) + [int(bits[2][:-1])]
            assert passed + failed == total, "Internal error, line=%s" % line
            datetime = line.split(",")[0]


    return submissions


def create_summary_ordered_by_assignments(s):
    r = {}
    for job, datetime, user, assignmentname, passed, failed in s:
        sub_so_far = r.get(assignmentname,[])
        try:
            tmp = [ x[2] for x in sub_so_far ].index(user)

            if assignmentname[0:3] == 'lab': #do not update
                pass

                #increase attempt counter but do not change the first set of data
                sub_so_far[tmp][-1] += 1
            else:
                attempts = sub_so_far[tmp][-1] + 1
                sub_so_far[tmp] = [job, datetime, user, passed, failed, attempts] #override older submission entry
        except ValueError:
            sub_so_far.append( [job, datetime, user, passed, failed, 1])
            r[assignmentname] = sub_so_far
    return r


def max_min_avg(l):
    n = len(l)
    return max(l),min(l),sum(l)/float(n)


def compute_statistics(subs):
    """Called with object r, like
    In [15]: r['training3']
    Out[15]:
    [[20, '2011-10-04 11:37:32', 'student1@example.org', 3, 0, 2],
     [34, '2011-10-05 10:33:32', 'student2@example.org', 3, 0, 1],
     [43, '2011-10-05 18:43:32', 'student3@example.org', 3, 0, 3],
     [52, '2011-10-05 21:26:32', 'student4@example.org', 3, 0, 2],
     [67, '2011-10-06 11:34:32', 'student5@example.org', 3, 0, 1]]
    """

    n = len(subs)
    passed = [s[3] for s in subs]
    total = [s[3]+s[4] for s in subs]

    max_pass, min_pass, avg_pass = max_min_avg(passed)
    avg_pass_pct = avg_pass / float(total[0])

    attempts = [s[5] for s in subs]
    max_attempt, min_attempt, avg_attempt = max_min_avg(attempts)

    return     max_pass, min_pass, avg_pass, avg_pass_pct,  max_attempt, min_attempt, avg_attempt



s = scan_log_file(logfile)
r = create_summary_ordered_by_assignments(s)

import time
print("Last updated: %s" % time.asctime())

for key in sorted(r.keys()):
    print "%15s : %3d unique submissions" %(key,len(r[key])),

    retval = compute_statistics(r[key])
    max_pass, min_pass, avg_pass, avg_pass_pct,  max_attempt, min_attempt, avg_attempt=retval

    print "pass : (max=%d, min=%d, avg=%4.2f=%4.1f%%)" % (max_pass, min_pass, avg_pass, avg_pass_pct*100),
    print "#( %d, %d, %4.2f )" % (max_attempt, min_attempt, avg_attempt)
