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


import re, os, string, random, time, exceptions

try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()

conf = __import__('config_' + Modulecode.lower())

import csvio

def debugprompt():
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed([])
    print "In send_mail"
    return ipshell

def gethash(dict,key,default=None):
    if dict.has_key(key):
        return dict[key]
    else:
        return default

def listindex(li,elem):
    pos=0
    for x in li:
        if x == elem:
            return pos
        else:
            pos=pos+1
    return None

def unlock_semaphore(lock):
    os.remove(lock)

def lock_semaphore(lockdir):
    # This provides robust, reliable locking semantics
    # even with filesystems such as NFS where flock()
    # may be troublesome...

    if(not(os.path.exists(lockdir))):
        os.mkdir(lockdir)

    lock_token ="lock-%s" % str(random.randint(0,1e40))
    lockfile=os.path.join(lockdir, lock_token)

    lock = open(lockfile,"w")
    lock.write( time.ctime(time.time()))
    lock.close()

    lockfiles=filter(lambda x: x[0:5] == "lock-", os.listdir(lockdir))

    other_lockfiles=filter(lambda x: x <> lock_token, lockfiles)

    if len(other_lockfiles)>0:
        # Some other process is also locking...
        print "WARNING: found other lock(s): %s (in %s)" % (repr(other_lockfiles),lockdir)
        unlock_semaphore(lockfile)
        return False

    return lockfile

def assignment_file_map(lab_name):
    return conf.assignments[lab_name]

def submitted_files_report(lab_name, user_files_by_type, report_in_detail=["mandatory","optional"]):

    lab_map = assignment_file_map(lab_name)
    report=[]

    for category in report_in_detail:
        report.append("=== %s files ===\n\n" % category)
        cfiles=[]

        user_files=gethash(user_files_by_type,category,[])

        for filename in lab_map.keys():
            (ftype,fpri)=lab_map[filename]
            if ftype == category:
                cfiles.append((fpri,filename))

        cfiles.sort()
        
        for (fpri,filename) in cfiles:
            tickbox="[   ]"
            if None<>listindex(user_files,filename):
                tickbox="[ X ]"

            report.append(" %s  %s\n" % (tickbox,filename))

        report.append("\n")    

    user_types=user_files_by_type.keys()
    user_types.sort()

    for utype in user_types:
        if None==listindex(report_in_detail,utype): # We already did these!

            report.append("--- %s files ---\n\n" % utype)
            user_files=user_files_by_type[utype][:]
            user_files.sort()
            for filename in user_files:
                report.append(" %s\n" % filename)

    return string.join(report,"")

def allowed_email_addresses():
    """Returns list of email addresses that are acceptable as sending submissions."""
    students = csvio.readcsv(conf.Studentlistcsvfile)
    return students.keys()

def database_name_for_user( datadir, login, studentlist = None ):
    #first try to find the name in the list
    if studentlist == None:
        students = csvio.readcsv(conf.Studentlistcsvfile)
        #this returns email address in lowercase

    login = login.lower()

    if login in students.keys():
        return students[login]
    elif login + conf.Domain in students.keys():
        return students[login + conf.Domain]
    else:
        print "Could not find login %s, searching in log files" % repr(login)
        #try to get data from logfiles
        userdir = os.path.join(datadir, login)
        try:
            f = open( os.path.join(userdir,'log.txt') )
        except IOError, mgs: # file does not exist
            realname = "_ (not in list, unknown)"
            return realname

        realname = "_ (not in list, unknown)"
    
        for line in f.readlines()[:-1]:
            bits = line.split(20*"-"+"studentdata:")
            if len(bits)==2:
                data = bits[1]
                login2, realname = data[:-1].split(":")
                realname = "_"+realname+" (not in list)"
                login2 = login2.lower()
                if not login2 == login:
                    print "line =",line
                    print "login=",login
                    print "login2=",login2
                    print "realame=",realname
                    print "directory name ",userdir
                    raise StandardError, "login does not match login2 from User's log.txt "
                break

        f.close()

    return realname

def user_realname( login ):
    db_name = database_name_for_user(conf.Submissiondir,login)
    name=db_name
    m=re.match(r"(\w+)\s*,\s*(\w+)",db_name)
    if m:
        name="%s %s" % (m.group(2),m.group(1))
    return name    

def find_users( directory ):
    usernames = []
    for dir in os.listdir(directory):
        if os.path.isdir(os.path.join(directory,dir)):
            usernames.append( dir )
    usernames.sort()

    return usernames

# NOTE: file_map has format:
# {'filename':(TYPE,PRIORITY) , ... }
# where files will be sorted by priority. TYPE will be "mandatory" or "optional"


def analyze_filenames(file_map, filenames, logger,ignored_files=["log.txt"]):
    files_by_type={}
    files_to_ignore={}

    def addfile(realname):
        if file_map.has_key(realname):
            (ftype,fpri)=file_map[realname]
        else:
            (ftype,fpri)=("unknown",0)
            
        if files_by_type.has_key(ftype):
            files_by_type[ftype].append((fpri,realname))
        else:
            files_by_type[ftype]=[(fpri,realname)]
        return ftype
    
    match_rx=[(re.escape(x)+"$",x) for x in file_map.keys()]


    for filename in filenames:

        logger.debug("checking file %s " % repr(filename))
        
        if re.match(r"part-\d+\.bin\b",filename):
            logger.debug( "Skipping %s" % repr(filename))
            continue
        if filename in ignored_files:
            logger.debug("Skipping %s" % repr(filename))
            continue
        if filename[0:5]=="_test":
            logger.debug("Skipping %s (pytest testing)" % repr(filename))
            continue

        #if file is of type ex1.py.1, ex1.py.2, etc
        if re.search(r"\.[0-9]+$",filename):
            logger.debug( "Skipping %s (only backup)" % repr(filename))
            continue
        else:
            logger.debug( "File %s seems not to be of .1 type" % repr(filename))

            our_filename=[n for (rx,n) in filter(lambda x:re.match(x[0],filename),match_rx)]
            
            if len(our_filename)>0:
                ftype=addfile(our_filename[0])
                logger.debug("  file %s type %s" % (repr(filename),repr(ftype)))
            else: # do not try to canonicalize UNKNOWN file
                ftype=addfile(filename)
                logger.debug("  file %s type %s" % (repr(filename),repr(ftype)))
                
    ret={}
    for key in files_by_type.keys():
        z=files_by_type[key][:]
        z.sort()
        ret[key]=[name for (pri,name) in z]

    return ret


class PyTestException(exceptions.Exception):
    pass
class RunConstrainedException(exceptions.Exception):
    pass
