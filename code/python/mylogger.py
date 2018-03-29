# This file is part of the TeTePy software
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


import logging, os.path

def attach_to_logfile( filename, level = logging.INFO, logname = None ):

    if logname == None:
        logname = filename

    # Check directory exists.
    if(not os.path.isdir(os.path.split(filename)[0])):
        os.makedirs((os.path.split(filename)[0]))
    
    logger = logging.getLogger( logname )
    hdlr = logging.FileHandler( filename )
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s#%(lineno)s %(message)s')    
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr) 
    logger.setLevel(level)

    #avoid opening loggers multiple times
    if len(logger.handlers) > 1:
        logger.removeHandler(logger.handlers[0])

    return logger

def logger_report(name):
    print("LOGGER REPORT {}".format(name))
    print("\tRootlogger:")
    rlog = logging.getLogger()
    print("    handlers: {}".format(rlog.handlers))
    print("     streams: {}".format([h.stream for h in rlog.handlers]))
    print("\tAll other loggers:")
    logger_names = logging.Logger.manager.loggerDict.keys()
    print("\tLoggers={}".format(logger_names))
    for loggername in logger_names:
        logger = logging.Logger.manager.loggerDict[loggername]
        print("\t  logger {}".format(logger))
        if hasattr(logger, 'handlers'):
            print("\t    handlers = {}".format(logger.handlers))
            if len(logger.handlers) > 0:
                print("\t      handler-streams = {}".format([h.stream for h in logger.handlers]))

def test():

    #logger_report('initial')
    log1 = attach_to_logfile( '/var/tmp/myxxapp.log' )
    log1.error('Starting log (this should be in logfile 1)')

    log2 = attach_to_logfile( '/var/tmp/myxxapp2.log' )
    log2.error('Starting log')

    log1.info('While this is just chatty')
    log1.warn('THis is a warning')

    log1.setLevel(logging.DEBUG)
    log2.setLevel(logging.DEBUG)

    log1.error('We have a problem')
    log1.info('While this is just chatty')

    log2.info('Ending')

    log1.info('Ending')


    #attach log3 to log1
    log3 = attach_to_logfile( '/var/tmp/myxxapp.log' )

    log3.info('test log3/1')
    logger_report('later')

    #log1.removeHandler('/var/tmp/myapp.log')

    log3.info('test log3/2')
    


if __name__=="__main__":
    test()

