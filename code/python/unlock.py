#!/usr/bin/env python

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

# Script to check for the presence of lock-files in the automatic
# testing system, and remove them, with the user's consent.
#
# NB: it is generally a bad idea to remove lockfiles from the running
# system until/unless the cause of the malfunction has been determined
# and a resolution put in place.  We therefore warn the user in this
# script.

import sys, string, os, lab_helpers, os.path

# Read Lockdir and subtest_locks from the relevant configuration files.
try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"

Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()
print "Module code is", Modulecode

try:
    conf = __import__('config_' + Modulecode.lower())
    Lockdir = conf.Lockdir
    subtest_locks = conf.subtest_locks
    outgoingmail_locks = conf.outgoingmail_locks
except:
    raise ImportError,"Couldn't import the configuration %s, or the variables Lockdir, subtest_locks, or outgoingmail_locks were undefined." % 'config_' + Modulecode.lower()

def find_locks(ldir):
    """Finds all files whose name begins with 'lock-' within the
    directory ldir, and returns their paths as a list.  Returns an
    empty list if no locks are found.  Recursively searches
    subdirectories of ldir."""
    lock_list = []
    lock_filename_start = "lock-"

    if(os.path.isdir(ldir)):
        for f in os.listdir(ldir):
            fname = os.path.join(ldir,f)
            if(os.path.isdir(fname)):
                lock_list.append(find_locks(ldir + fname))
            if(os.path.isfile(fname) and f[0:len(lock_filename_start)] == lock_filename_start):
                    lock_list.append(os.path.join(ldir,fname))
    else:
        print("Warning: lockfile directory {0:s} does not exist or is not a directory.\n".format(ldir))
    return lock_list

if __name__ == "__main__":

    # Find the locks
    print("Looking for lock files in:\n")
    print("\n".join([Lockdir, subtest_locks, outgoingmail_locks]))
    lock_list = find_locks(Lockdir) + find_locks(subtest_locks) + find_locks(outgoingmail_locks)
    if len(lock_list) == 0:
        print("No locks found, quitting.".format(Lockdir,subtest_locks))
        sys.exit(os.EX_OK)

    # Present user a list and a warning
    print("The following {0:d} lockfiles were found:".format(len(lock_list)))
    for filename in lock_list:
        print("{0:s}".format(filename))
    print("\nWARNING: On a live system, locks must be removed\nonly when their cause is known and rectified.\n")
    confirm = ""
    while (confirm.lower() != "y" and confirm.lower() != "n"):
        confirm = raw_input("Do you wish to remove these locks? [y/n]: ")

    if confirm.lower() == "n":
        print("Not removing lock files.  Exiting.")
        sys.exit(os.EX_OK)

    # Remove if the user requests
    for lock in lock_list:
        lab_helpers.unlock_semaphore(lock)
    print("{0:d} locks removed.".format(len(lock_list)))
    sys.exit(os.EX_OK)
