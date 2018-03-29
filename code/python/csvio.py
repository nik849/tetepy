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


import csv
import logging, mylogger, os

try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()

conf = __import__('config_' + Modulecode.lower())

log_global = mylogger.attach_to_logfile(conf.Logfile, level = conf.log_level)

def readcsv(filename):
    """returns dictionary with student emails (without @soton.ac.uk)
    as keys and real names as value

    """
    students = {}
    stream = {} # dictionary data for stream
    f = open(filename,'rb')
    csvdata = csv.reader(f)
    for item in csvdata:
        try:
            (name, email, stream) = item
        except ValueError:
            if len(item) == 2:
                name, email = item
                print "Warning Couldn't find stream for %s %s" % (item[0],item[1])
                stream = "unknown"
            if len(item) == 0:
                continue  # skip to next.
            if item[0].startswith('#'):
                continue  # is a commented line, ignore
            else:
                raise ValueError,"Non-blank line with other than 2 or 3 fields found in readcsv()."

        # some finetuning of email adressess and ill-formatted names
        email = email.lower()
        #(i) add space after comma
        name = name.replace(',',', ')
        #(ii) remove space at end of string
        if name[-1] == " ":
            name = name[:-1]
        students[email]=name+' '+stream

    return students

def readcsv_group(filename):
    """Returns a dictionary with student emails as keys and tuples
    ('real name','group') as values, for a student list file called
    filename, formatted thus:
    "User,Test1","example1@one.example","Campus1"
    "User,Test2","example2@one.example","Campus2"
    "User,Test3","example3@one.example","Campus1"
    """
    students = {}
    f = open(filename,'rb')
    csvdata = csv.reader(f)
    for item in csvdata:
        try:
            (name, email, group) = item
        except ValueError:
            if len(item) == 2:
                name, email = item
                log_global.warn("csvio.py: readcsv_group: Couldn't find group for {0} {1}, setting to 'unknown'".format(item[0],item[1]))
                print "Warning Couldn't find group for %s %s" % (item[0],item[1])
                group = "unknown"
            if len(item) == 0:
                continue # skip blank lines.
            if item[0].startswith('#'):
                continue  # is a commented line, ignore
            if (len(item) == 1 or len(item)) > 3:
                raise ValueError, "Read wrong number of fields (i.e. 1 or >3)"

        #some finetuning of email adressess
        email = email.lower()
        #(i) add space after comma
        name = name.replace(',',', ')
        #(ii) remove space at end of string
        if name[-1] == " ":
            name = name[:-1]
        students[email]=(name, group)

    return students

if __name__ == "__main__":
    filename = 'nameemail.csv'

    print('Running readcsv() on {0}:\n'.format(filename))
    s = readcsv(filename)
    print s

    print('\nRunning readcsv_group() on {0}:\n'.format(filename))
    s = readcsv_group(filename)
    print s

