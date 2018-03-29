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


import cPickle, datetime, email, errno, fcntl, logging, os, os.path, shutil
import smtplib, time

# Reads outgoing mail queue, tries to send each item therein.
# Dequeues those which were sent successfully, and leaves those which
# were not sent in the queue to re-try next time the script is called.

from lab_helpers import lock_semaphore, unlock_semaphore

live = True

import mylogger
import enqueue_outgoing_mails

# Find module code and read correct config file.
try:
    import pwd
except:
    raise ImportError,"Couldn't import pwd -- only available on unix systems"
Modulecode = pwd.getpwuid(os.getuid()).pw_name.upper()

conf = __import__('config_' + Modulecode.lower())

def read_smtp_socket_errfile():
    """Reads the statistics file off disk for recent SMTP error
    conditions, returns a dictionary."""

    with open(conf.smtp_error_file,'r') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        smtp_socket_errors = cPickle.load(f)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return smtp_socket_errors

def record_smtp_socket_success():
    """Resets the SMTP socket error statistics file - called when
    there are no SMTP errors in a session."""

    smtp_socket_errors = read_smtp_socket_errfile()

    # If there were errors before this success, notify admin we
    # succeeded and are about to reset error counters.  Also log the
    # fact.
    if (smtp_socket_errors.has_key('smtp_failed_run_count')):
        err_count = smtp_socket_errors['smtp_failed_run_count']
    else:
        err_count = 0

    if err_count > 0:
        subject = ("INFORMATION: SMTP socket error cleared in {0:s} "
                   "at {1:s}".format(conf.ModulecodeSubjectLine,time.asctime()))
        text = ("After {0:d} SMTP socket errors, delivery of emails has succeeded.\n"
                "Will reset error counters.".format(err_count))

        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress, text, subject, conf )

        log_global.info("After {0:d} failures, SMTP socket error cleared".format(err_count))
        log_global.info("Emailed sysadmin")

    # Clear error counter and timestamps, set success time to now.
    smtp_socket_errors = {
        'smtp_failed_run_count':0,
        'smtp_first_fail_time':'',
        'smtp_last_fail_time':'',
        'smtp_last_success_time':time.asctime(),
        'smtp_last_admin_mail_time':time.asctime(),
        'smtp_error_messages':[]
        }

    # Save to disk.
    with open(conf.smtp_error_file,'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        f.truncate(0)
        cPickle.dump(smtp_socket_errors, f)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def process_smtp_socket_error(err_msg):
    """Records the time and error message for an SMTP socket error and
    emails the administrator if appropriate.  Updates the SMTP socket
    error statistics file when email is sent."""

    def email_admin_smtp_socket_err(continuing=0):
        ins,outs = os.popen4('tail -n 100 '+conf.outgoingmail_logfile)

        text = ("There have been {0:d} consecutive SMTP socket errors "
                "since {1:s}\n\n".format(smtp_socket_errors['smtp_failed_run_count'],
                                       smtp_socket_errors['smtp_first_fail_time']))
        text += "SMTP errors with their counts were:\n"
        for this_err in set(smtp_socket_errors['smtp_error_messages']):
            text += repr ((this_err, smtp_socket_errors['smtp_error_messages'].count(this_err))) + "\n"
        text += "\nRecent outgoing mail processor log file entries follow:\n\n" + outs.read()

        if(continuing==0):
            subject = ("WARNING: SMTP socket error - malfunction in {0:s} at {1:s}"
                       "!!!".format(conf.ModulecodeSubjectLine,time.asctime()))
        else:
            subject = ("WARNING: Continuing SMTP socket error - malfunction in {0:s} at {1:s}"
                       "!!!".format(conf.ModulecodeSubjectLine,time.asctime()))

        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress, text, subject)


    smtp_socket_errors = read_smtp_socket_errfile()

    # Record details of the error.
    smtp_socket_errors['smtp_failed_run_count'] += 1
    if(len(smtp_socket_errors['smtp_first_fail_time']) == 0):
        smtp_socket_errors['smtp_first_fail_time'] = time.asctime()
    smtp_socket_errors['smtp_last_fail_time'] = time.asctime()
    smtp_socket_errors['smtp_error_messages'].append((err_msg.errno, err_msg.strerror))


    # Email admin if this is error number "conf.smtp_error_threshold"
    if(smtp_socket_errors['smtp_failed_run_count'] == conf.smtp_error_threshold):
        email_admin_smtp_socket_err()
        smtp_socket_errors['smtp_last_admin_mail_time'] = time.asctime()
        log_global.info("Emailed sysadmin")


    # Email admin if we last emailed admin more than
    # "conf.smtp_error_repeat" hours ago.
    last_mail_time = time.mktime(time.strptime(smtp_socket_errors['smtp_last_admin_mail_time']))
    now = time.time()
    # NB: if system clock changes this may lead to inaccurately timed
    # emails.  Recommend running ntpd in any case.
    repeat_seconds = 3600 * conf.smtp_error_repeat
    if((now - last_mail_time) >= repeat_seconds):
        email_admin_smtp_socket_err(continuing=1)
        smtp_socket_errors['smtp_last_admin_mail_time'] = time.asctime()
        log_global.info("Emailed sysadmin")


    # Save updated error information.
    with open(conf.smtp_error_file,'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0)
        f.truncate(0)
        cPickle.dump(smtp_socket_errors, f)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_queue_names():
    """Read from disk all the filenames in directory
    conf.outgoingmail_queue, return a list of those whose names begin
    with 'm' (i.e., those which are outgoing mails in the queue).  If
    the directory is nonexistant, it is created and the action is
    logged."""

    if not os.path.exists(conf.outgoingmail_queue):
        log_global.info("Directory for outgoing mail queue {0:s} not found, "
                        "will create it now.".format(conf.outgoingmail_queue))
        os.makedirs(conf.outgoingmail_queue)

    entryfiles = filter(lambda x: x[0:1] == "m", os.listdir(conf.outgoingmail_queue))
    entryfilepaths = map(lambda x : os.path.join(conf.outgoingmail_queue,x), entryfiles)
    return entryfilepaths

def send_email_from_file(filename):
    """Reads filename, which is expected to be in the format returned
    by the as_string() method of an email.Message.Message obejct,
    parses it into an email.Message.Message object as an approximation
    of validation, and tries to send it via SMTP.  On success it
    returns os.EX_OK, otherwise it returns None or a failure code from
    the os module."""

    # Read file as string
    with open(filename,'r') as f:
        msg_string = f.read()

    # Parse string as email message, ensure that the message has at
    # least certain fields filled in, move to the rejected directory
    # and warn administrator if we fail.
    try:
        msg = email.message_from_string(msg_string)
        assert msg["To"].count("@") > 0
        assert msg["From"].count("@") > 0
        assert len(msg["Subject"]) > 0
        assert len(msg.get_payload()) > 0

    except Exception, errmesg:
        log_global.warn("Parsing email from queued file {0:s} failed, "
                        "rejecting. ({1:s})".format(filename, errmesg))

        text = ("WARNING: invalid entry in outgoing mail queue.\n"
                "Exception message was: {0:s}\n"
                "The rest of this message contains the entry.\n".format(errmesg))
        text += "\n" + 40*"=" + "\n"
        text += msg_string + "\n" + 40*"=" + "\n"
        subject = ("WARNING: Invalid outgoing mail found in queue in "
                   "{0:s} at {1:s}".format(conf.ModulecodeSubjectLine,
                                           time.asctime()))

        enqueue_outgoing_mails.send_text_message(conf.SysadminEmail, conf.ModuleEmailAddress,text, subject)

        name_only = os.path.split(filename)[-1]

        if not os.path.exists(conf.outgoingmail_rejected):
            log_global.info("Directory for rejected outgoing mail {0:s} "
                            "does not exist, will create it now.".format(conf.outgoingmail_rejected))
            os.makedirs(conf.outgoingmail_rejected)

        shutil.move(filename, os.path.join(conf.outgoingmail_rejected, name_only))
        return os.EX_DATAERR

    # Try sending the mail.
    return send_mail(msg)

def mailqueue_pop(filename):
    """Removes the file named filename from the outgoing mail queue,
    saves it in a processed directory, and logs this action."""

    # If filename is a fully-qualified path, it is left unchanged.
    filepath = os.path.join(conf.outgoingmail_queue,filename)

    # Move message to processed directory so that it is clear to see
    # that it has been sent.
    processed_directory=conf.outgoingmail_processed
    if not os.path.exists(processed_directory):
        log_global.info("Directory for processed outgoing mail {0:s} "
                        "does not exist, will create it now.".format(processed_directory))
        os.makedirs(processed_directory)

    processedpath = os.path.join(processed_directory,os.path.split(filepath)[-1])
    os.rename(filepath,processedpath)

    log_global.info("Removed '%s' from outgoing mail queue" % filename)


def process_queue():
    # 1 - read filenames, with full paths, get as list.
    queued_filenames = read_queue_names()

    if (len(queued_filenames) == 0):
        record_smtp_socket_success()
        log_global.info("Queue empty, recorded success, quitting")
    else:
        log_global.info("Found %d mail(s) (%s)" % (len(queued_filenames),queued_filenames))

    # 2 - for each filename, read contents, parse, try to send.
    for filename in queued_filenames:
        log_global.info("Processing mail %s" % filename)

        status = send_email_from_file(filename)

        if(status == os.EX_OK):
            # 2a --- if success, dequeue and move on
            mailqueue_pop(filename)
        else:
            # 2b --- if failure, leave in queue, log, and move on.
            log_global.warn("Delivering email from queued file {0:s} failed.".format(filename))

def startup(log_level=logging.INFO):
    # Set up logging
    log_global = mylogger.attach_to_logfile(conf.outgoingmail_logfile, level = log_level)
    enqueue_outgoing_mails.log_global=log_global #let functions in that module use the same logger
    enqueue_outgoing_mails.conf=conf

    # Ensure the existence of needed directories
    for dirname in (os.path.split(conf.outgoingmail_queue)[0],
                    os.path.split(conf.outgoingmail_logfile)[0],
                    os.path.split(conf.smtp_error_file)[0]):
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

    # Set up SMTP error statistics handling.
    if not (os.path.exists(conf.smtp_error_file)):
        with open(conf.smtp_error_file,'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            cPickle.dump({}, f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        record_smtp_socket_success()

    # Log startup
    log_global.debug(40*"=")
    log_global.debug("Starting program up")
    log_global.debug(40*"=")
    log_global.debug("============= Starting ===========")

    return log_global

def send_mail( msg, debug = 0 ):
    """Sends a mail (in email-message format). Expect msg to be of type
    email.Message.Message(), retuns os.EX_OK on success, None or an os.*
    error code on error.
    """

    # turn this off for off-line testing
    network = 1

    mailfrom = msg["From"]

    # For multiple recipients:
    # msg['To'] ought to look like 'recipient1, recipient2'
    # whilst smtp.sendmail() should get a list ['recipient1', 'recipient2']
    if msg["To"].count(",") == 0:
        # single recipient
        mailto = msg["To"]
    else:
        mailto = [recip.replace(" ","") for recip in msg["To"].split(",")]

    assert mailfrom, "No from-addr given: %s" % repr(mailfrom)
    assert mailto, "No to-addr given: %s" % repr(mailto)

    log_global.info("send_mail(): email from %s to %s" %
                    (repr(mailfrom),repr(mailto)))

    log_global.debug("send_mail(): Beginning of content is\n%s" % msg.as_string()[0:1000*80])
    if debug:
          print "Beginning of content is",msg.as_string()[0:1000*80]

    log_global.info("sending email from %s to %s" % (repr(mailfrom),repr(mailto)))

    if not(network):
        log_global.warn("Not sending email (not in network mode)")
        print "==BEGIN Sent Email========================="
        print msg.as_string()[0:1*80]
        print "==END Sent Email==========================="
        return os.EX_OK
    else:
        log_global.info("(deliver email to %s via smtp to %s)" % (repr(mailto),repr(conf.smtp)))
        import socket

        try:
            smtp = smtplib.SMTP(conf.smtp)
            smtp.set_debuglevel(0) #put in 1 for messages to stdout/stderr
            smtp.sendmail(mailfrom, mailto, msg.as_string())
            smtp.quit()
            log_global.debug("finished sending email to %s" % repr(mailto))
            record_smtp_socket_success()
            return os.EX_OK

        except socket.error,err_msg:
            # This arises most commonly when the SMTP server is
            # overloaded or unavailable - our main goal is to keep
            # re-trying this message (so return None to keep it in the
            # queue), and notify admin from time to time, as per
            # config settings.
            log_global.warn("smtp delivery failed, will retry on next queue run, error: {0:s}".format(err_msg))
            process_smtp_socket_error(err_msg)

            return None

        except smtplib.SMTPRecipientsRefused,err_msg:
            # Mostly occurs if we mistakenly reply to spam.  It is not
            # desired to stop the system in this case, so we inform
            # the administrator, including the message that we could
            # not send to its original recipient, and carry on.  We
            # return EX_OK in order that the undeliverable message
            # be removed from the queue of messages for sending.
            undelivered_string = msg.as_string()
            text = ("WARNING: could not deliver email.\n"
                    "The rest of this message contains the mail that was undeliverable,\n"
                    "followed by the error log and exception error message.\n\n\n")
            text += "\n" + 40*"=" + "\n"
            text += undelivered_string + "\n" + 40*"=" + "\n"
            ins,outs = os.popen4('tail -n 100 '+conf.Logfile)
            text += outs.read()+'\n'+'Error message is:\n'+str(err_msg)
            subject = "WARNING: Malfunction in %s at %s (probably spam) (could not deliver email but will carry on, might have been spam)" % (conf.ModulecodeSubjectLine,time.asctime())
            enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress,text, subject)
            log_global.info("Emailed sysadmin")
            log_global.warning("Failed to send email to %s" % repr(mailto))

            record_smtp_socket_success()

            return os.EX_OK 

    raise Exception,"send_mail(): something should have returned, execution should not reach here."


if __name__ == "__main__":

    global log_global

    log_global = startup(log_level=conf.log_level)
    lock = lock_semaphore(conf.outgoingmail_locks)

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
                ins,outs = os.popen4('tail -n 100 '+conf.outgoingmail_logfile)
                text = outs.read()
                subject = "URGENT: Malfunction in process_outgoing_mails %s at %s !!!" % (conf.ModulecodeSubjectLine,time.asctime())
                enqueue_outgoing_mails.send_text_message( conf.SysadminEmail, conf.ModuleEmailAddress,text, subject)
                log_global.info("Leaving now (not removing lockfile).")
                raise
        else:
            process_queue()
            unlock_semaphore(lock)

    import time
    f=open(conf.outgoingmail_pulsefile,'w')
    data = {'now-secs':time.time(),'now-ascii':time.ctime(),'module':conf.ModulecodeSubjectLine,
            'what':"process-outgoingmail"}
    f.write("%s" % repr(data))
    f.close()
    log_global.debug("About to leave, updated pulse.")
