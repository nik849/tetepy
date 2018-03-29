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


import email, email.Utils, types, os, os.path, mimetypes, string, time, smtplib
import logging, exceptions, fcntl, sys, shutil, email.MIMEBase, email.MIMEText
import re, random, pprint, shelve, errno, textwrap

import mylogger

import enqueue_outgoing_mails


try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()

print "Module code is", Modulecode

conf = __import__('config_' + Modulecode.lower())

from lab_helpers import *
import lab_helpers

log_global=None
log_level = conf.log_level
debug = 0

if 'subtest_tests' in dir(conf):
    pass #expect tests
else:
    #create empty fake entries
    conf.subtest_tests = {} #no tests to be done
    subtest_queue = '/non-existent'


class myException(exceptions.Exception):
    pass

# Regex for mail daemon
_rx_email_daemon=r"daemon|deamon|fetchmail-daemon|FETCHMAIL-DAEMON|cron|root|postmaster"

# Regex for From-escaping in emails
_rx_from_escape=">(>*From (.|\n)*)"

# User cannot upload files with such names:
blacklisted_filenames=["log.txt","s.py"]


def is_true(x):
    if x:
        return True
    else:
        return False

def bundle_files_in_directory_in_email( directory,to,From,Subject ):
    """bundle all files in directory and return as email object

    This is taken from Matthew Cowles
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/86674  """

    import cStringIO
    import base64
    import email.Generator
    import email.Message
    import os
    import quopri

    mainMsg=email.Message.Message()
    mainMsg["To"]=to
    mainMsg["From"]=From
    mainMsg["Subject"]=Subject
    mainMsg["Mime-version"]="1.0"
    mainMsg["Content-type"]="Multipart/mixed"
    mainMsg.preamble="Mime message\n"
    mainMsg.epilogue="" # To ensure that message ends with newline
    # Get names of plain files
    filenames = []
    for f in os.listdir(directory):
        if os.path.isfile(os.path.join(directory,f)):
            filenames.append(f)

    for fileName in filenames:
        # print "working on",fileName
        contentType,ignored=mimetypes.guess_type(fileName)
        if contentType==None: # If no guess, use generic opaque type
            contentType="application/octet-stream"
        contentsEncoded=cStringIO.StringIO()
        f=open(os.path.join(directory,fileName),"rb")
        mainType=contentType[:contentType.find("/")]
        if mainType=="text":
            cte="quoted-printable"
            quopri.encode(f,contentsEncoded,1) # 1 for encode tabs
        else:
            cte="base64"
            base64.encode(f,contentsEncoded)
        f.close()
        subMsg=email.Message.Message()
        subMsg.add_header("Content-type",contentType,name=fileName)
        subMsg.add_header("Content-transfer-encoding",cte)
        subMsg.set_payload(contentsEncoded.getvalue())
        contentsEncoded.close()
        mainMsg.attach(subMsg)

    return mainMsg

def retrieve_assignment(assignment,message,student_dir,real_name,email_addr,logger):

    logger.info("Retrieving files for %s" % repr(assignment))

    (username,domain)=email_address_username_and_domain(email_addr)

    #get list of files in student_dir
    submission_dir = os.path.join(student_dir,assignment)

    if os.path.exists ( submission_dir ):
        submitted_files = os.listdir( submission_dir  )
    else:
        errormail = replymail_error( message, "It seems that you have not yet submitted any files." )
        append_mail_to_mailbox( errormail, username, logger, "(outgoing error mail: no files submitted->retrieval is impossible)" )
        return None

    files_by_type = analyze_filenames(assignment_file_map(assignment), submitted_files, logger)

    report = submitted_files_report(assignment, files_by_type)

    body  = ["Dear %s (%s),\n\n" % (real_name,email_addr)]

    body.append("Here is a list of your files found on the server for assignment '%s':\n\n" % assignment)
    body.append(report)

    body.append("\n\nPlease find attached to the _next_ email these files\n")
    body.append("that you submitted for '%s'.\n\n" %assignment)
    body.append("(In addition, there may be one (or more) files named\n")
    body.append("'part00?.bin' which contain the body of your email and can \n")
    body.append("be ignored.)\n\n")

    subject = "[%s] summary of submitted files for '%s' (%s)" % ( conf.ModulecodeSubjectLine, assignment, time.asctime()) 


    mail = enqueue_outgoing_mails.send_text_message( email_addr, conf.ModuleEmailAddress, string.join(body,""), subject)
    append_mail_to_mailbox( mail, username, logger, "(outgoing retrieval report mail)" )

    #now do retrieve the files and mail those

    subject = "[%s] retrieved files for '%s' (%s)" % ( conf.ModulecodeSubjectLine, assignment, time.asctime())
    From = conf.ModuleEmailAddress
    to = email_addr

    retrieval_return_mail = bundle_files_in_directory_in_email( submission_dir,to,From,subject)
    text =  enqueue_outgoing_mails.send_message(retrieval_return_mail)
    append_mail_to_mailbox( text, 'test', logger, "(outgoing retrieval mail)" )

    logger.info("Sent retrieval mail for %s" % repr(assignment))


def is_retrieval (subject):
    """check whether the first part of the subject is 'retrieve'"""
    #catch empty subject
    if subject == None:
        return False

    return is_true(re.match(r"\s*retrieve\s+",subject,re.IGNORECASE))

def extract_attachments(msg):
    """Extracts attachments from msg (which is a Message Object from
    module 'email') and returns them in a dictionary:
    key is name of file and value is content.
    """

    log_local = ""

    result = {}

    counter = 0
    for part in msg.walk():

        # multipart/* are just containers
        if part.get_content_type() == 'multipart':
            continue
        filename = part.get_filename()
        if not(filename) or (listindex(blacklisted_filenames,filename)):
            counter += 1
            log_local += "Could not get file_name of attachment. "
            filename = 'part-%03d%s' % (counter, ".bin")
        log_local+="Assigned filename=%s to attachment. " % repr(filename)
        counter += 1

        result[filename]= part.get_payload(decode=1)

        log_local += "Extracting attachment %i with name %s. " % (counter,repr(filename))

    return (result, log_local)


def save_attachments( msg, dir ):
    #connect to log file for user
    logger = mylogger.attach_to_logfile( os.path.join(dir,'log.txt' ), level = log_level )

    def keep_older_versions_of_this_file( filename ):

        def change_name_version(newfilename,filename,changes=0):
            #use just the filename (without path) for logging:
            log_nfn = os.path.split(newfilename)[1]
            log_fn = os.path.split(filename)[1]

            logger.debug("Entering change_name_version %s <- %s " % (repr(log_nfn),repr(log_fn)))
            try:
                version = int(newfilename.split('.')[-1])
                root = ".".join(newfilename.split('.')[0:-1])
            except ValueError,msg:
                logger.error( "problem with filename %s in increase_counter" % repr(filename))
                raise ValueError,msg

            if os.path.exists(newfilename):
                logger.debug("file: %s exists -- recursive retry!" % repr(log_nfn))
                changes = change_name_version(root+'.'+str(version+1),root+'.'+str(version),changes)
            else:
                logger.debug("Found last file: %s" % repr(log_nfn))

            logger.debug( "About to rename %s to %s" % (repr(log_fn),repr(log_nfn)))
            os.rename(filename,newfilename)
            return changes+1

        changes = None
        if os.path.exists(filename):
            changes = change_name_version(filename+'.1',filename)
            return changes

    #save_attachements starts here
    (att, logstr) = extract_attachments( msg )

    logger.info("============ save_attachments =======(%s)" % repr(dir))
    logger.debug( logstr )

    counter = 0
    for filename in att.keys():
        counter += 1
        logger.debug("Need to extract attachment %i (named %s)" % (counter,repr(filename)))
        if att[filename] == None:
            logger.warn("Found empty attachement %i (att[%s]==None), Skipping" % (counter,repr(filename)))
            continue

        changes = keep_older_versions_of_this_file(os.path.join(dir, filename))

        if changes:
            logger.info("Extracting attachment %i (named %s, keeping %d old copies)" % (counter,repr(filename),changes) )
        else:
            logger.info("Extracting attachment %i (named %s)" % (counter,repr(filename)) )

        fp = open(os.path.join(dir, filename), 'wb')
        fp.write( att[filename] )
        fp.close()

    return att


def append_mail_to_mailbox( mail, student_login, logger, logcomment = "" ):
    username = student_login
    mailboxdir = os.path.join(conf.Maildir, username)

    logger.info("Appending Email to %s %s" % (repr(mailboxdir),logcomment))

    f_out = open ( mailboxdir , 'a' )
    f_out.write( mail )
    f_out.close()


def split_mailbox_into_strings( inbox ):

    """Takes filename of inbox containing one or more email, and
    returns list of strings, each containing one email

    """

    fin = open(inbox,"r")
    mailstrings = []
    mailtext = []
    linecounter = 0

    while 1:
        line = fin.readline()
        linecounter += 1
        if (linecounter%10000)==0:
            log_global.debug("read line %d: %s" % (linecounter,line[0:30]))
        if not line:
            if debug:
                print "reached end of file"

            #if we have found any data 
            if mailtext != []:
                # append last data (as string) to list of emails
                mailstrings.append( string.join(mailtext,'') )
            else:
                #this indicates an empty inbox file
                pass
            break   #reached end of file

        if line[0:5] == "From ":   #found new email, start new file
            log_global.debug("Found new 'From' in mailbox file")
            #this will make the first list entry 'None'. Remove that before we return
            mailstrings.append( string.join(mailtext,'') )
            mailtext = [line]
            if debug:
                print "Starting new mailf file"

        # Emails that contain "From " on a single line get that escaped to ">From",
        # and ">From" will be escaped to ">>From" etc.

        fmatch=re.match(_rx_from_escape,line)
        if fmatch:
            line=fmatch.group(1)

        #write line to currently active mailfile
        try:
            mailtext.append(line)
        except IndexError:
            log_global.exception("Error: file %s didn't start with 'From'" % repr(inbox))
            raise IndexError
        except:
          print "Came across some other error while reading inbox"
          sys.exit(1)

    fin.close()

    return mailstrings[1:] 


def email_address_username_and_domain(addr):
    """Maps an email address such as user@example.org to username
    and domain part. 

    Note: this routine splits at the last '@' sign, having checked
    only that the given address contains at least one '@' sign and at
    least one '.' character.

    It is possible to have a valid email address with multiple '@'
    signs, (see e.g. the informal RFC3696), and this routine should
    work in these cases.
    """

    if (addr.count('@') < 1 or addr.count('.') < 1):
        subject = "WARNING: Invalid address on incoming email from %s" % repr(addr)
        text = ("Email from %s, address either has fewer than one '.' character,\n"
                "or fewer than one '@' character." % repr(addr))
        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress, text, subject)
        log_global.info("Emailed sysadmin about regex failure of splitting address %s. " % addr)
        raise StandardError,"Unusual email address : '%s" % repr(addr)

    try:
        parts = addr.split('@')
        domain = parts[-1]
        username = ''
        for p in parts[0:-2]:
            username = username + p + '@'
        username = username + parts[-2]
    except:
        # otherwise send message to admin
        subject = "WARNING: Address split failed on incoming email from %s" % repr(addr)
        text = "Email from %s. We split to find name='%s' and domain='%s'" % (addr,username,domain)
        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress, text, subject)
        log_global.info("Emailed sysadmin about failure of splitting address %s. " % addr)
        raise StandardError,"Unusual email address : '%s" % repr(addr)

    return username, domain


def get_email_metadata( the_email, debug = 0 ):
    """expects email as msg object from email.Message.Message()

    Returns sender, login, domain, number of attachments and subject line.
    """

    #identify student
    (real_name, email_addr) = email.Utils.parseaddr( the_email["From"] )

    (username,domain) = email_address_username_and_domain(email_addr)
    subject = str(the_email["Subject"])

    payload = the_email.get_payload()
    #compute number of attachments
    if type( payload ) == types.ListType:
        n_attach = len( payload )
    else:
        n_attach = 1

    if real_name=='':
        log_global.info("Incoming email from username='%s', subject='%s' has no realname. Will look up in student list file" % (username,subject))
        real_name = user_realname(username)

    result= (real_name, email_addr, username, domain, n_attach, subject)
    return result


def sending_domain_okay(domain,known_domains=["example.org","example.org.uk"]):
    pattern = "(%s)$" % reduce(lambda x,y:(x+"|"+y),["\\b"+re.escape(d) for d in known_domains])
    # This turns known_domains into word-boundary-delimited matches, i.e.
    # soton.ac.uk -> \bsoton\.ac\.uk, then builds a termimal-or-pattern from that.

    return is_true(re.search(pattern,domain,re.IGNORECASE))


def replymail_confirm_submission(real_name, email_addr, text, subject, assignment, valid_attachments, q_id=None):
    """ Sends an email to the student named real_name at address
    email_addr, which consists of a confirmation of receipt of their
    email whose subject should be in subject, with a q_id (if
    assigned) followed by the contents of the traing text.

    Returns the sent message as string if there are no attachments, or
    None."""

    intro = "Dear "+real_name+" ("+email_addr+"),\n\n" + \
    textwrap.fill("this email confirms the receipt of your email\n" + \
    "with subject %s at %s." %( repr(subject), time.asctime()))+"\n\n"

    if q_id:
        if valid_attachments:
            intro += textwrap.fill("Your submitted files have been added to the "+\
                "testing queue (id=%s).\n" % (q_id) + \
                "You will receive a separate email with the "+\
                "testing results.")+"\n\n"

        newsubject = "["+conf.ModulecodeSubjectLine+"] Submission Confirmation "\
            +str(assignment)+" ("+time.asctime()+")"

    else:
        intro += textwrap.fill("Your files will be archived.")+"\n\n"
        newsubject = "["+conf.ModulecodeSubjectLine+"] Archive confirmation "+str(assignment)+" ("+time.asctime()+")"

    return enqueue_outgoing_mails.send_text_message( email_addr, conf.ModuleEmailAddress, intro+text, newsubject)

def replymail_error( msg, text, CC_to_admin=False, maxsend=None ):
    """Takes message 'msg' and composes a reply to the sender with body 'text'.

    If CC_to_admin is true, the message will be sent to the sysadmin as well.

    The idea of maxsend is that if maxsend is given, we will only attempt maxsend time
    to deliver email to the same email address. This could be useful if we engage in
    infinite loops with external spam. The code isn't written for this yet.
    """

    real_name, email_addr = email.Utils.parseaddr( msg["From"] )

    log_global.debug("in replymail_error (to %s, subj: %s)" % (real_name,msg["Subject"]))

    text = "Dear "+str(real_name)+" ("+str(email_addr)+"),\n\n" + \
           "An error occured while parsing your email with subject\n" + \
           repr(msg["Subject"])+" received at "+time.asctime()+":\n\n"+ \
           text

    if CC_to_admin:
        subject = "["+conf.ModulecodeSubjectLine+"-admin] submission error, "+time.ctime(time.time())+", "+str(msg["Subject"])
        enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress, text, subject)

    subject = "["+conf.ModulecodeSubjectLine+"] submission error, "+time.ctime(time.time())+", "+str(msg["Subject"])

    return enqueue_outgoing_mails.send_text_message( email_addr, conf.ModuleEmailAddress, text, subject)



def check_required_files(file_map, file_names):
    """ Given a file_map for the assignment, the names of all
    attachments taken from the current email in file_names, and a
    logger, this function checks that each file marked mandatory was
    extracted from an attachment. 

    Returns (missing_required_files, all_mandatory_files_present),
    where missing_required_files is a list of names of missing
    required files and all_mandatory_files_present is a boolean."""

    all_mandatory_files_present = True
    missing_required_files=[]

    # Loop over all filenames known for this assignment.
    for assignment_file_name in file_map.keys():
        (ftype, fpriority) = file_map[assignment_file_name]

        # File is mandatory but was not attached.
        if ((ftype == 'mandatory') and (assignment_file_name not in file_names)):
                all_mandatory_files_present = False
                missing_required_files.append(assignment_file_name)

    return (all_mandatory_files_present, missing_required_files)

def submission_reply_report(student_dir, attachments, lab_name):
    """ Returns a tuple (valid_attachments, reply) where:

    valid_attachments = True if all the files marked 'mandatory' are
    present in the attachments passed in, False otherwise.

    reply is a string containing a report that gives details of which
    files were saved from the student submission and which files were
    already stored in student_dir."""

    valid_attachments = False
    report=[]

    log_local = mylogger.attach_to_logfile( os.path.join( student_dir,'log.txt' ), level = logging.DEBUG )

    log_global.debug("Attachment keys: %s" % repr(attachments.keys()))

    files_by_type = analyze_filenames(assignment_file_map(lab_name), attachments.keys(), log_global)

    log_global.debug("files_by_type: %s" % repr(files_by_type))

    (valid_attachments, missing_required_files) = check_required_files(assignment_file_map(lab_name), attachments.keys())
    nr_files=reduce(lambda sf,x:sf+len(files_by_type[x]),files_by_type.keys(),0)

    log_global.info("attachments: %s files_by_type: %s"%(repr(attachments.keys()),repr(files_by_type)))

    # All required files were extracted.
    if (nr_files > 0 and valid_attachments == True):
        report.append("### Files found in this submission for assessment '%s' ###\n\n" % lab_name)

        ftypes=files_by_type.keys()
        ftypes.sort()
        for ftype in ftypes:
            files=files_by_type[ftype]
            fstr=string.join(files,"\n   ")
            report.append(" %-12s:\n   %s\n" % (ftype,fstr))

        report.append("\n")

    # Some files were extracted but not all the required ones (or
    # files not correctly named, ...)
    elif (len(missing_required_files) > 0):
        report.append("### WARNING: this submission will not be tested.\n\n")
        report.append("### Not all the required files were extracted from your email.\n")
        report.append("### Please check that you have attached all the required files.\n\n")

        report.append("### Files found in this submission for assessment '%s':\n\n" % lab_name)

        ftypes=files_by_type.keys()
        ftypes.sort()
        for ftype in ftypes:
            files=files_by_type[ftype]
            fstr=string.join(files,"\n   ")
            report.append(" %-12s:\n   %s\n" % (ftype,fstr))

        report.append("\n")

        report.append("### Required files not found in this submission:\n\n")
        for filename in missing_required_files:
            report.append("   %-12s\n" % filename)
        report.append("\n\n")

    # No files extracted.
    else:
        report.append("WARNING: no files have been extracted from your email.\n")
        report.append("         (Maybe you have forgotten to attach them?)\n\n")

    #get list of files in student_dir
    submitted_files = os.listdir(os.path.join(student_dir,lab_name))

    #remove log files from these and separate into known and unknown files
    submitted_by_type = analyze_filenames(assignment_file_map(lab_name), submitted_files, log_global)

    report.append("-----------------------------------------------------\n\n")
    report.append("In summary, you have submitted these files for assessment '%s'.\n" % lab_name)
    report.append("Please note that the files listed below may be from previous submission\n")
    report.append("attempts, where these are allowed:\n\n")

    report.append(submitted_files_report(lab_name, submitted_by_type))

    report.append("\n\n == IMPORTANT: Keep this email as a receipt of your submission ==\n")

    return (valid_attachments, string.join(report,""))



def check_maildaemon( msg, from_addr, domain ):

    if re.search(_rx_email_daemon,from_addr,re.IGNORECASE):
        log_global.critical("Received a msg from a mailing daemon (X)! ("+msg["From"]+")")
        log_global.critical("Forwarding it to administrator (%s)." % (conf.SysadminEmail) )

        # We need to delete the "To" key entry first:
        del msg["To"]
        # Then write new value
        msg["To"] = conf.SysadminEmail

        original_subject = msg["Subject"] 
        del msg["Subject"]
        msg["Subject"] = "Urgent: [%s] email from daemon: %s" % (conf.ModulecodeSubjectLine,repr(original_subject))

        del msg["From"]
        msg["From"] = conf.ModuleEmailAddress

        enqueue_outgoing_mails.mailqueue_push(msg)
        return 1

    #check that the email is not from ourselves
    if string.count( from_addr.lower(), conf.Modulecode.lower()):
        log_global.critical("Received a msg from myself! ("+msg["From"]+")")
        log_global.critical("Forwarding it to administrator (%s)." % repr(conf.SysadminEmail) )

        subject = "Urgent: [%s] email from system (danger of loop): %s" % (conf.ModulecodeSubjectLine,repr(msg["Subject"]))
        sendmail = enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress, msg.as_string(), subject)
        append_mail_to_mailbox( sendmail, conf.sysadminmailfolder, log_global, "(outgoing mail to SysadminEmail (myself-loop))" )
        return 1

    if string.count(domain.lower(), "twitter"):
        log_global.info("Received a msg from twitter: ("+msg["From"]+")")
        log_global.info("Forwarding it to administrator (%s)." % (conf.SysadminEmail) )

        # We need to delete the "To" key entry first:
        del msg["To"]
        #Then write new value
        msg["To"] = conf.SysadminEmail

        original_subject = msg["Subject"] 
        del msg["Subject"]
        msg["Subject"] = "[%s] Twitter writes: %s" % (\
            conf.ModulecodeSubjectLine,repr(original_subject))

        del msg["From"]
        msg["From"] = conf.ModuleEmailAddress

        enqueue_outgoing_mails.mailqueue_push(msg)
        return 1

    return 0


def subject_identification( assignments, submission, log_global):
    """Only sensible submissions are labX (with X integer number) and
    coursework.

    submission is a string that contains the subject line.

    Assignments is coming through from configuration file.

    return None if could not identify
    """

    debug = 0
    if debug:
        print 'trying to identify %20s\t: ' % submission,


    if submission == None:
        log_global.warn("unparseable subject: '%s' " % submission)
        return None

    if submission == '':
        log_global.warn("unparseable empty string in subject: '%s' " % submission)
        return None

    assert len(assignments.keys()) > 0, "Internal error"

    match_spam=re.match(r"\{Spam?\}(.*)",submission)
    if match_spam:
        submission=match_spam.group(1)
        log_global.warn("stripping off '{Spam?}' from subject line: %s " % repr(submission))

    forward_reply_keywords = ['Fwd:', 'Forward:', 'Re:', 'Reply:']
    for kwd in forward_reply_keywords:
        if kwd in submission:
            log_global.warn("stripping off '{}' from subject line: {} ".format(
                kwd, submission))
            submission = submission.replace(kwd, '')
            continue

    #The list of relevant keywords we are after is
    keys = [x.lower() for x in assignments.keys()] #this is ['lab1','lab2',...,'lab6','cw']

    #check whether subject line is preceeded by "{Spam?} ". If so,
    #then the mailing system thinks it is spam. This could be wrong, however.
    #we therefore get rid of this, and log it.

    canonicalized_submission=submission.replace(' ','').lower()

    #do trivial test (i.e. input is 'lab1' or 'cw')

    if canonicalized_submission in keys:
        return canonicalized_submission

    log_global.warn("unparseable string: %s / %s" % (submission, canonicalized_submission))
    return None


def subtestqueue_push(metadata):

    counterfile = os.path.join(conf.subtest_queue,'.maxid')

    if not os.path.exists(counterfile):
        #make sure directory exists
        os.system('mkdir -p %s' % conf.subtest_queue)
        open(counterfile,'w').write("0")

    f = open(counterfile, 'r+')
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    q_id = int(f.read())+1
    f.seek(0)
    f.truncate(0)
    f.write("%d" % q_id)
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    f.close()

    filename = "s%05d-%s-%s" % (q_id,metadata['assignment'],metadata['login'])
    log_global.info("Injecting job (id=%d) to testing-queue entry '%s'" % (q_id,filename))

    metadata['id']=q_id
    metadata['qfilename']=filename
    metadata['qfilepath']=os.path.join(conf.subtest_queue,filename)

    assert os.path.exists(os.path.join(conf.subtest_queue,filename))==False,"Internal error"
    f=open(os.path.join(conf.subtest_queue,filename),'w')
    f.write(pprint.pformat(metadata))
    f.close()

    return q_id


def process_inbox():
    log_global.debug("process_inbox: lockdire=%s" % conf.Lockdir)

    semaphore=lock_semaphore(conf.Lockdir)

    if(not semaphore):
        os.system('echo "\n---------------\n`date`"')
        print "It seems that another version of this script is running already... Leaving cowardly."
        print "Remove LOCKFILE in %s to overrride this" % repr(conf.Lockdir)
        log_global.warn("Found LOCK, exiting now!")
        return None

    # now check whether there is anything in the mailbox file. If
    # not, there is no point carrying on

    #test whether mailbox file exists
    if not os.path.exists(conf.inbox):
        raise StandardError, "Inbox file %s does not exist" % repr(conf.inbox)

    print("Trying to read from inbox {}".format(conf.inbox))
    if int(os.popen("wc -c "+conf.inbox).read().split()[0]) == 0:
      log_global.info("Inbox is empty. Quitting." )
      unlock_semaphore(semaphore)
      return None

    #lock mailbox file
    finbox = open(conf.inbox, 'r+')
    fcntl.flock(finbox.fileno(), fcntl.LOCK_EX)

    # copy file to tmp-file before we start analysing
    tempname =  conf.tmpname
    log_global.debug("Copying %s to %s" % (repr(conf.inbox),repr(tempname)))
    shutil.copyfile( conf.inbox, tempname )
    shutil.copymode( conf.inbox, tempname ) # also copy permissions

    #now delete mailbox
    finbox.seek(0)
    finbox.truncate(0)
    #unlock
    fcntl.flock(finbox.fileno(), fcntl.LOCK_UN)
    finbox.close()

    mails = split_mailbox_into_strings( tempname )

    log_global.info("=====> found %d emails in inbox %s" % (len(mails),repr(conf.inbox)))

    counter = 0

    for mail in mails:
        counter += 1

        log_global.debug("(1) processing mail %d" % counter)

        msg = email.message_from_string( mail )

        (real_name, email_addr, email_login, domain, n_attach, subject) = get_email_metadata( msg )

        #keep copy of email in folder with ALL incoming email (just in case)
        append_mail_to_mailbox( mail, '_allincomingemail', log_global, "(keep copy of all incoming email in _allincomingemail)" )
        log_global.info("%i: from %s (%s), ATT: %d, SUB: %s" % (counter,repr(real_name),repr(email_addr),n_attach,repr(subject)))

        #check for special events (are we getting mail from a daemon?)
        if check_maildaemon( msg, email_login, domain ):
            log_global.info("(2a) sent email to administrator. Skipping to next student")
            continue

        #Check whether we need to check for particular users
        if conf.allow_only_emails_given_in_list:
            log_global.debug("(3a) only users given in list are allowed")
            if email_addr.lower() in map(string.lower,lab_helpers.allowed_email_addresses()):
                log_global.debug("Incoming email from %s is in list of acceptable emails" % email_addr)
            else:
                log_global.warn("rejecting email from addresss %s (not in allowed list)" % (email_addr))
                error_msg = replymail_error(msg, conf.TXT_address,CC_to_admin=True,maxsend=None)
                append_mail_to_mailbox( error_msg, '_errors', log_global, "(outgoing error mail: sending email_address (%s) unknown)" % (email_addr) )
                continue
        else:     #do not check for address in list. Instead, check domain
            log_global.debug("(3b) Allow all users from right domain")
            if True: #set to False to allow emails from any domain (initially for St Poelten Summer School July 2011)
                if not sending_domain_okay( domain ):
                    log_global.warn("rejecting email from %s (wrong domain)" % (email_addr))
                    error_msg = replymail_error(msg, conf.TXT_Domain,CC_to_admin=True)
                    append_mail_to_mailbox( error_msg, '_errors', log_global, "(outgoing error mail: wrong domain (%s))" % (email_addr) )
                    continue

        #now we know the student
        log_global.debug("(2) domain okay, student is %s (%s)" % (repr(email_login),repr(real_name)))

        #check that the directory exists:
        student_dirpart = email_login
        student_dir = os.path.join( conf.Submissiondir, student_dirpart)
        if not os.path.exists( student_dir ):
            log_global.debug("Creating directory %s" % (repr(student_dir)))
            os.mkdir(student_dir)
        else:
            log_global.debug("   Student directory exists (%s)" % (repr(student_dir)))

        #connect to log file for user
        logger = mylogger.attach_to_logfile( os.path.join( conf.Submissiondir, email_login,'log.txt' ), level = log_level )
        logger.info(20*"-"+"studentdata:"+repr(email_login)+":"+repr(real_name))

        #keep copy of mail in Maildir
        append_mail_to_mailbox( mail, email_login, logger, "(incoming mail from {})".format(email_login) )

        retrieval = False
        #check whether this is a retrieval attempt
        if is_retrieval(subject):
            logger.info("Identified retrieval attempt (%s)" % (repr(subject)) )
            retrieval = True

            #chop off 'retrieve' from subject line
            remaining_subject=re.match(r"\s*retrieve\s+(.*)",subject,re.IGNORECASE).group(1)

            assignment = subject_identification( conf.assignments, remaining_subject, log_global)
            log_global.warn("RETR: S=%s rems=%s a=%s" % (subject,remaining_subject,assignment))

        else:
            #check lab makes sense
            assignment = subject_identification( conf.assignments, subject, log_global)

        if assignment == None:
            log_global.warn("rejecting email from %s (unknown submission: %s)" % (repr(email_addr),repr(subject)))
            logger.warn("rejecting email (unknown submission: %s)" % (repr(subject)))

            errormail = replymail_error(msg, conf.TXT_Submission)
            append_mail_to_mailbox( errormail, email_login, logger, "(outgoing error mail: couldn't parse assignment)" )

            continue #no need to carry on further
        else:
            if retrieval:
                retrieve_assignment(assignment,msg,student_dir,real_name,email_addr,logger)
                continue  # no need to carry on further

        #normal submission continues here
        logger.info("found submission for %s (%s)" % (assignment,repr(subject)))
        log_global.info("found submission for %s from %s" % (assignment,repr(email_login)))

        #check that the directory exists:
        student_lab_dir = os.path.join( conf.Submissiondir, student_dirpart, assignment )
        if not os.path.exists( student_lab_dir ):
            log_global.debug("Creating directory %s" % repr(student_lab_dir))
            os.mkdir( student_lab_dir )

         #check that files make sense
        attachments = save_attachments( msg, student_lab_dir )

        #generate report to be mailed to the student, and set
        #valid_attachments to True if all the required files were
        #attached to *this message*
        (valid_attachments, reply) = submission_reply_report(student_dir, attachments, assignment)

        #If we have the required attachments, check whether submission
        #tests are associated with this assignment, and push a job to
        #the test queue

        log_global.debug("Have-found-valid_attachments = {}".format(valid_attachments))

        we_have_a_testfile_for_this_submission = assignment in conf.subtest_tests.keys()

        log_global.debug("Have-we-got-a-test-file-for-this-submission = {}"\
            .format(we_have_a_testfile_for_this_submission))

        if we_have_a_testfile_for_this_submission and valid_attachments:
            log_global.debug("Found assignment {} in subtest.keys.".format(assignment))
            subtest_metadata = {'student_lab_dir':student_lab_dir,
                                'assignment':assignment,
                                'real_name':real_name,
                                'email':email_addr,
                                'login':email_login,
                                'subject':subject,
                                'time':time.asctime()}
            q_id = subtestqueue_push(subtest_metadata) #read Queue-id
            # Compose and send an email to the student, based on the
            # report generated above.
            confirm_mail = replymail_confirm_submission(real_name, email_addr, reply, subject, assignment, valid_attachments, q_id)
            append_mail_to_mailbox(confirm_mail, email_login, logger, "(outgoing confirmation mail; job submitted for testing)")

        elif valid_attachments == True and we_have_a_testfile_for_this_submission == False:
            log_global.info("Did not find assignment {} in subtest.keys={}".format(assignment, conf.subtest_tests.keys()))
            q_id = None
            confirm_mail = replymail_confirm_submission(real_name, email_addr, reply, subject, assignment, valid_attachments, q_id)
            append_mail_to_mailbox(confirm_mail, email_login, logger, "(outgoing confirmation email - no testing to follow)")
        elif valid_attachments == False:
            # the function 'submission_reply_report' above sends an error message in this case so we don't need to do anything here.
            error_mail = replymail_error(msg, reply)
            append_mail_to_mailbox(error_mail, email_login, logger, "(outgoing error mail - attachmenns not valid)")
        else:
            raise RuntimeError("This should be impossible")

    log_global.info("Finish.proc. %d emails. Rm %s and quit" % (len(mails),tempname)
    unlock_semaphore(semaphore)


def startup():
    """check all directories are in place"""

    if not os.path.exists( conf.Homedir ):
        raise StandardError, "%s does not exist (but is Homedir)" % conf.Homedir
    log_global = mylogger.attach_to_logfile( conf.Logfile, level = log_level )

    print "reached startup(), logfile is %s" % conf.Logfile

    log_global.debug(40*"=")
    log_global.debug("Starting program up")
    log_global.debug(40*"=")

    #check directories
    dirs = [conf.Maildir,conf.Submissiondir,conf.Tempdir]

    for dir in dirs:
        if not os.path.exists( dir ):
            log_global.info("Creating directory %s" % ( dir ) )
            os.mkdir( dir )

    return log_global


if __name__ == "__main__":
    #set everything up
    log_global = startup()
    enqueue_outgoing_mails.log_global = log_global
    enqueue_outgoing_mails.conf = conf

    live = True

    if live:
        try:
            process_inbox()
        except:
            log_global.exception("Something went wrong (caught globally)")

            log_global.critical("Preparing email to sysadmin (%s)" % repr(conf.SysadminEmail))
            ins,outs = os.popen4('tail -n 100 '+conf.Logfile)
            text = outs.read()
            subject = "URGENT: Malfunction in %s at %s !!!" % (conf.ModulecodeSubjectLine,time.asctime())
            enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress,text, subject)
            log_global.info("Leaving now (not removing lockfile).")

    else:
        process_inbox()

    import datetime,time
    f=open(conf.pulsefile,'w')
    data = {'now-secs':time.time(),'now-ascii':time.ctime(),'module':conf.ModulecodeSubjectLine,
            'what':"process-emails"}
    f.write("%s" % repr(data))
    f.close()
    log_global.debug("About to leave, updated pulse.")

