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

import email.Message, errno, fcntl, os, os.path

log_global = None
conf = None

def send_text_message( mailto, mailfrom,  text, subject, html=False ):

    msg=email.Message.Message()

    msg["Subject"] = subject
    msg["From"] = mailfrom
    msg["To"] = mailto

    if html:
        html_header="<html><body>"
        html_footer="</body></html>"
    else:
        html_header=html_footer=""
    
    msg.set_payload(html_header+
                    text+"\n\n"+70*"-"+"\n\n"+conf.disclaimer+
                    +html_footer)

    return send_message(msg)



def send_message(msg, return_msg_as_string = 1):

    mailqueue_push(msg)

    #can only return message as string that has no attachments
    if return_msg_as_string:
        return msg.as_string(unixfrom=1)
    else:
        return None

def mailqueue_push(msg):
    # All outgoing mail should be placed into the queue via this function.

    counterfile = os.path.join(conf.outgoingmail_queue,'.maxid')

    # Ensure the directory exists and we have a counter.
    if not os.path.exists(counterfile):
        try:
            os.makedirs(conf.outgoingmail_queue)
        except OSError as e:
            if e.errno == errno.EEXIST:
                pass
            else:
                raise

        with open(counterfile,'w') as cf:
            cf.write("0")

    # Get next id and increment counter
    with open(counterfile,'r+') as f:
        # Exclusively lock counterfile, update it
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        q_id = int(f.read())+1
        f.seek(0)
        f.truncate(0)
        f.write("%d" % q_id)
        # Unlock
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    # Use some msg fields to determine filename for queued email.
    if msg["To"].count(",") == 0:
        # single recipient
        to = msg["To"]
    else:
        to = msg["To"].split(",")[0]
    filename = "m%010d-%s" % (q_id,to)
    log_global.info("Enqueueing outgoing mail (id=%d) to queue entry '%s'" % (q_id,filename))

    # Save the string representation of the message in the sending queue.
    assert os.path.exists(os.path.join(conf.outgoingmail_queue,filename))==False, \
        "Internal error: will not overwrite outgoing email {0:s}".format(filename)
    with open(os.path.join(conf.outgoingmail_queue,filename),'w') as f:
        f.write(msg.as_string())

    return q_id
