#!/usr/bin/python
#
# Full mail test. Send and email via SMTP and read in via IMAP/POP
#

import sys
import random
import string
import email
import time
import ldap
import os
import random

from ConfigParser import RawConfigParser, ParsingError
from smtplib import SMTP, SMTP_SSL
from email.mime.text import MIMEText
from smtplib import SSLFakeFile
from datetime import datetime
from imaplib import IMAP4_SSL
from poplib import POP3_SSL
from copy import copy
import smtplib
import imaplib
import poplib
import ssl
import email
import pdb

def die(msg):
    print msg
    sys.exit(1)


class MySSLFakeFile(SSLFakeFile):
    def read(self, size):
        return self.sslobj.read(size)


class MyIMAP4(imaplib.IMAP4):
    def starttls(self):
        imaplib.Commands['STARTTLS'] = ('NONAUTH',)
        result = self._simple_command('STARTTLS')
        if result[0] != 'OK':
            raise self.error('START TLS failed.')
        self.sock = ssl.wrap_socket(self.sock) 
        self.file = MySSLFakeFile(self.sock)
        result = self.capability()
        if result[0] != 'OK':
            raise self.abort('CAPABILITY failed.')


class MyPOP3(poplib.POP3):
    def starttls(self):
        result = self._shortcmd('STLS')
        if not result.startswith('+OK'):
            raise poplib.error_proto('STLS failed.')
        self.sock = ssl.wrap_socket(self.sock)
        self.file = MySSLFakeFile(self.sock)


class MailTest():
    def __init__(self, config):
        self.config = config
        for section in config.sections():
            for option in config.options(section):
                value = config.get(section, option)
                if value.isdigit():
                    value = int(value)
                elif value.lower() in [ 'false', 'no' ]:
                    value = False
                elif value.lower() in [ 'true', 'yes' ]:
                    value = True
                setattr(self, option, value)

        users_file = self.users
        self.users = []
        users_fd = open(users_file)
        for line in users_fd:
            line = line.strip()
            user = line.split()
            self.users.append(user)

        if not hasattr(self, 'smtp'):
            die('smtp server is required.')

        if not hasattr(self, 'imap') and not hasattr(self, 'pop'):
            die('imap or pop server is required.')

        if hasattr(self, 'imap'):
            self.imap = self.imap.split()

        if hasattr(self, 'pop'):
            self.pop = self.pop.split()

        self.smtp = self.smtp.split()

        self.smtp_errors = 0
        self.imap_errors = 0
        self.pop_errors = 0
        self.sent = 0
        self.received = 0
        self.pop_recvd = 0
        self.imap_recvd = 0

        print self.log
        self.log_fd = open(self.log, 'a')

    def logf(self, msg):
        self.log_fd.write(datetime.now().isoformat() + ' ' + msg + "\n")

    def run(self):
        for i in range(0, int(self.children)):
            if not os.fork():
                self.nro = i
                self.run_child()

        try:
            os.waitpid(0, 0)
        except OSError:
            print 'No child process'

    def run_child(self):
        for i in range(0, self.count):
            self.sender = random.choice(self.users)
            self.recipient = random.choice(self.users)
            try:
                self.send_mail()
                time.sleep(int(self.sleep))
                self.recv_mail()
                time.sleep(int(self.sleep))
            except smtplib.SMTPException, e:
                self.smtp_errors += 1
                self.logf('SMTP error: %s, user=%s' % (str(e), self.sender))
            except imaplib.IMAP4.error, e:
                self.imap_errors += 1
                self.logf('IMAP error: %s, user=%s' % (str(e), self.recipient))
            except poplib.error_proto, e:
                self.pop_errors += 1
                self.logf('POP error: %s, user=%s' % (str(e), self.recipient))

            print '----'
            print 'Sent: ', self.sent
            print 'Recv: ', self.received
            print 'IMAP: ', self.imap_recvd
            print 'POP: ', self.pop_recvd
            print 'SMTP errors: ', self.smtp_errors
            print 'Imap errors: ', self.imap_errors
            print 'POP errors: ', self.pop_errors

    def random_msg(self):
        subject =  ''.join(random.choice(string.letters) for i in xrange(40))
        body =  ''.join(random.choice(string.letters) for i in xrange(999))
        msg = MIMEText(body)
        msg['subject'] = subject
        #msg['to'] = self.recipient
        #msg['from'] = self.sender
        #print msg.as_string()

        return msg

    def send_mail(self):
        smtp = random.choice(self.smtp)
        print 'SMTP', smtp, self.sender
        if self.smtp_ssl:
            smtp = SMTP_SSL(smtp, self.smtp_port)
        else:
            smtp = SMTP(smtp, self.smtp_port)

        if self.smtp_start_tls:
            smtp.starttls()

        if self.smtp_auth:
            smtp.login(*self.sender)

        self.subjects = []
        for i in range(0, self.msg_per_connection):
            msg = self.random_msg()
            self.subjects.append(msg["subject"])
            smtp.sendmail(self.sender[0], self.recipient[0],
                        msg.as_string())
            self.sent += 1

    def recv_mail(self):
        if self.pop_recv:
            self.pop_subjects = copy(self.subjects)
            for i in range(0, int(self.fetchretries)):
                if self.pop_recv_mail():
                    break
                time.sleep(int(self.fetchwait))

        if self.imap_recv:
            self.imap_recv_mail()

    def pop_recv_mail(self):
        pop = random.choice(self.pop)
        print 'POP', pop, self.recipient
        if self.pop_ssl:
            pop = POP3_SSL(pop, self.pop_port)
        else:
            pop = MyPOP3(pop, self.pop_port)

        if self.pop_start_tls:
            pop.starttls()

        result = pop.user(self.recipient[0])
        if not result.startswith('+OK'):
            raise Exception('POP user login failed: ' + str(result))

        result = pop.pass_(self.recipient[1])
        if not result.startswith('+OK'):
            raise Exception('POP pass login failed: ' + str(result))

        result = pop.list()
        if not result[0].startswith('+OK'):
            raise Exception('POP list failed: ' + str(result))

        for msg_nro in result[1]:
            msg_nro = msg_nro.split()[0]
            msg = pop.retr(msg_nro)
            if not result[0].startswith('+OK'):
                raise Exception('POP retr failed: ' + str(result))

            msg = '\r\n'.join(msg[1])
            msg = email.message_from_string(msg)

            if msg['subject'] in self.pop_subjects:
                self.pop_subjects.remove(msg['subject'])
                self.received += 1
                self.pop_recvd += 1

        #XXX: report this. It's a bug of poplib. It should close the 
        #socket in object destruction.
        pop.quit()

	if len(self.subjects) == 0:
		return True

        return False

    def imap_recv_mail(self):
        imap = random.choice(self.imap)
        print 'IMAP', imap, self.recipient
        if self.imap_ssl:
            imap = IMAP4_SSL(imap, self.imap_port)
        else:
            imap = MyIMAP4(imap, self.imap_port)

        if self.imap_start_tls:
            imap.starttls()

        resp = imap.login(*self.recipient)
        if resp[0] != 'OK':
            raise Exception('IMAP login fail.')

        imap.select()
        for subject in self.subjects:
            if self.imap_get_msg(imap, subject):
                self.received += 1
                self.imap_recvd += 1

        imap.logout()

    def imap_get_msg(self, imap, subject):
        for i in range(0, int(self.fetchretries)):
            msgs = imap.search(None, 'SUBJECT', '"%s"' % (subject))
            for msgnum in msgs[1][0].split():
                msg = imap.fetch(msgnum, '(RFC822)')
                msg = msg[1][0][1]
                msg = email.message_from_string(msg)
                if msg['Subject'] == subject:
                    return True

            time.sleep(int(self.fetchwait))

        return False


if len(sys.argv) != 2:
    die("I need a test file!")

try:
    test = RawConfigParser()
    test.read(sys.argv[1])
except ParsingError, e:
    die("Test file error: " + e)

test = MailTest(test)
test.run()

