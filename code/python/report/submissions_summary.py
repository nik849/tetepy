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
    print "Provide logfile as command line argument, please"
    sys.exit(1)

logfile = sys.argv[1]


def scan_log_file(logfile):
    """Returns list of tuples with jobs that were injected to testing queue.

    Each tuple contains (jobnumber, datetime, user, assignmentname)
    """

    f = open(logfile)

    submissions = []

    for line in f:
        if 'Injecting' in line:
            bits = line.split("testing-queue entry 's")[1].split('-', 2)
            job, assignmentname, user = bits
            datetime = line.split(",")[0]
            submissions.append( (job, datetime, user, assignmentname) )

    return submissions


def create_summary_ordered_by_assignments(s):
    r = {}
    for job, datetime, user, assignmentname in s:
        sub_so_far = r.get(assignmentname,[])
        try:
            tmp = [ x[2] for x in sub_so_far ].index(user)
            sub_so_far[tmp] = (job, datetime, user) #override older submission entry
        except ValueError:
            sub_so_far.append( (job, datetime, user))
            r[assignmentname] = sub_so_far

            pass #no entry for this user yet

    return r



s = scan_log_file(logfile)
r = create_summary_ordered_by_assignments(s)
import time
print "Updated: ",time.asctime()

for key in sorted(r.keys()):
    print "%15s : %d unique submissions" %(key,len(r[key]))
