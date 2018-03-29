/*
 *
 * This file is part of the TeTePy software
 * 
 * Copyright (c) 2017, 2018, University of Southampton
 * All rights reserved.
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 * 
 * * Redistributions of source code must retain the above copyright notice, this
 *   list of conditions and the following disclaimer.
 * 
 * * Redistributions in binary form must reproduce the above copyright notice,
 *   this list of conditions and the following disclaimer in the documentation
 *   and/or other materials provided with the distribution.
 * 
 * * Neither the name of the copyright holder nor the names of its
 *   contributors may be used to endorse or promote products derived from
 *   this software without specific prior written permission.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 * CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
 * OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
* 
 */

/*
 *
 * A primitive wrapper to set up a constrained environment to run
 * student-submitted code in:
 *  - Using a special, nonprivileged user
 *  - Constraining resource usage
 *
 *
 * Compile and install as follows:
 *
 * gcc -std=c99 -DPYTEST=\"/usr/bin/py.test-3\" -D_XOPEN_SOURCE=600 \
 * -Wall -o run_constrained_pytest run_constrained_pytest.c && \
 * /usr/bin/sudo -- chown run_stud:run_stud run_constrained_pytest && \
 * /usr/bin/sudo -- chmod 6550 run_constrained_pytest
 *
 * We allow the definition of the path to py.test via the -DPYTEST flag
 * which gives different modules the felxibility to choose a different
 * py.test executable (e.g. to pick Py2/Py3, or a different release for
 * PEP8 harmonisation with the machines in the Common Learning Spaces).
 * If not definition is given in the command line, a default path of
 * /usr/local/bin/py.test is used.
 *
 * NB: the " characters are escaped in the example above to protect them
 * from the shell
 *
 * We define _XOPEN_SOURCE=600 in order to expose definitions for SUSv3
 * (UNIX03; i.e. POSIX.1-2001 base spec + XSI extension).  This is
 * required so that the compiler can see definitions of the setenv
 * function (along with setreuid and setregid, which are included from
 * UNIX 98 (SUSv2, _XOPEN_SOURCE=500))
 *
 */

#include <sys/types.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <stdlib.h>
#include <stdio.h>
#include <regex.h>
#include <unistd.h>
#include <grp.h>
#include <errno.h>
#include <string.h>
#include <signal.h>

#ifndef PYTEST
#define PYTEST "/usr/local/bin/py.test"
#endif

static char* py_call = PYTEST;

static char *wrapped_env[]={"PYTHONPATH=/home/run_stud/code/python-libs","DISPLAY=:2.0","HOME=/home/run_stud","USER=run_stud","PATH=/usr/local/bin:/bin:/usr/bin:/usr/local/X11/bin:/usr/X11/bin","LANG=C","TERM=ansi","SHELL=/bin/sh","LANGUAGE=uk",0};

static char* rxstr_path_and_file="^\\(.*\\)/\\([^/]*\\)$";

static void err_sys(const char* str) {
  perror(str);
  fflush(NULL);   /* flushes all open stdio output streams */
  exit(1);
}

static void aiee(char str[]) {
  fprintf(stderr, "AIEE: %s\n",str);
  fflush(stderr);
  exit(1);
}

static rlim_t min(rlim_t a, rlim_t b) {
  return a<b?a:b;
}

static void handle_sigchld(int n) {
  /* Child process died -- and so do we... */
  exit(0);
}

static void handle_sigterm(int n) {
  /* Got sigterm... quit... */
  exit(0);
}

int main(int argc, char **argv, char **envp)
{
  int i;
  uid_t uid;
  gid_t gid;
  int child_pid;
  char **pycall;
  static regex_t rx_path_and_file;
  static struct rlimit limit;
  static regmatch_t matches[3];
  int len_path,len_script;
  char *path, *script;

  /* First of all, we fork. In fact, parent and child process are using the
     same I/O channels here, and all I/O will be handled by the child.
     The only purpose of the parent is to give the caller an opportunity
     to finish it off by sending a kill signal...
   */

  if(-1==(child_pid=fork())) {
    err_sys("fork() failure!");
  }

  if(0!=child_pid) /* This is the parent process... */
    {
      if(signal(SIGTERM,&handle_sigterm) == SIG_ERR)
	err_sys("can't catch SIGTERM");
      if(signal(SIGCHLD,&handle_sigchld) == SIG_ERR)
	err_sys("can't catch SIGCHLD");
      for(;;) {
	pause();
      }
    }

  /* If we got here, we are the child process... */


  if(argc<2) {
    aiee("Need script to run!");
  }

  if(0!=(regcomp(&rx_path_and_file,rxstr_path_and_file,0))) {
    aiee("regcomp() failed!");
  }

  uid=geteuid();
  gid=getegid();
  if(0!=setreuid(uid,uid))
    err_sys("setuid() failed");
  if(0!=setregid(gid,gid))
    err_sys("setgid() failed");

  if(0!=(regexec(&rx_path_and_file,argv[1],3,matches,0))) {
    aiee("regexec() failed on script path!");
  }

  if(NULL==(pycall=malloc(sizeof(char*)*(1+argc)))) {
    err_sys("malloc() failure!");
  }

  len_path=matches[1].rm_eo-matches[1].rm_so;
  len_script=matches[2].rm_eo-matches[2].rm_so;

  if(   (NULL==(path=malloc(len_path+1)))
	|| (NULL==(script=malloc(len_script+1)))) {
    err_sys("malloc() failure!");
  }

  for(i=0;i<len_path;i++) {
    path[i]=argv[1][matches[1].rm_so+i];
  }
  path[i]=0;

  for(i=0;i<len_script;i++) {
    script[i]=argv[1][matches[2].rm_so+i];
  }
  script[i]=0;

  if(0!=chdir(path)) {
    err_sys("chdir() failure");
  }


  pycall[0]=py_call;
  pycall[1]=script;
  for(i=2;i<argc;i++) {
    pycall[i] = argv[i];
  }
  pycall[argc]=0;

  /* Enforcing limits... limit to the minimum of any existing limit or
     our chosen value. */

  /* Address space (virtual memory): 500 MB */
  if(0!=getrlimit(RLIMIT_AS,&limit))
    err_sys("getrlimit() failure!\n");

  /* A limit of 500MB virtual memory  */
   limit.rlim_cur=limit.rlim_max=min(limit.rlim_max,500*1048576);
  if(0!=setrlimit(RLIMIT_AS,&limit))
    err_sys("setrlimit() failure!\n");

  /* CPU time: 90 seconds -- we check the execution time from Python
     which makes it easier to identify that an infinite loop is the problem
     and to give feedback to the student. The time specified here
     is only a hard-coded upper limit. */
  if(0!=getrlimit(RLIMIT_CPU,&limit))
    err_sys("getrlimit() failure!\n");

  limit.rlim_cur = limit.rlim_max = min(limit.rlim_max,90UL); 
  if(0!=setrlimit(RLIMIT_CPU,&limit))
    err_sys("setrlimit() failure!\n");

  /* Maximum disk file size: 1 MiB (protects against using all the
	 * disk space capturing stdout of unterminated loops etc)*/
  if(0!=getrlimit(RLIMIT_FSIZE,&limit))
    err_sys("getrlimit() failure for RLIMIT_FSIZE!\n");

  limit.rlim_cur=limit.rlim_max=min(limit.rlim_max,1048576);
  if(0!=setrlimit(RLIMIT_FSIZE,&limit))
    err_sys("setrlimit() failure for RLIMIT_FSIZE!\n");

  /* Resident Set Size: 500 MB */
  if(0!=getrlimit(RLIMIT_RSS,&limit))
    err_sys("getrlimit() failure!\n");
  limit.rlim_cur=limit.rlim_max=min(limit.rlim_max,500*1048576);

  if(0!=setrlimit(RLIMIT_RSS,&limit))
    err_sys("setrlimit() failure!\n");

  if(0!=setenv("DISPLAY",":2.0",1))
    err_sys("setenv() on $DISPLAY failed!");

  if(0!=setenv("HOME","/home/run_stud",1))
    err_sys("setenv() on $HOME failed!");

  if(0!=execve(pycall[0],pycall,wrapped_env)) {
    fprintf(stderr, "Called execve with arguments:\n");

    fprintf(stderr, "filename: %s\n", pycall[0]);

    for(int i=0; i <= argc; i++) {
      fprintf(stderr, "argv[%d]: %s\n", i, pycall[i]);
    }

    int i = 0;
    while(wrapped_env[i] != 0) {
      fprintf(stderr, "envp[%d] = %s\n", i, wrapped_env[i]);
      i++;
    }
    fprintf(stderr, "envp[%d] = %s\n", i, wrapped_env[i]); 

    err_sys("execve() failed!");
  }
  
  return 0; 
}

