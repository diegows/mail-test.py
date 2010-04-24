#!/usr/bin/python
#
# Full mail test. Send and email via SMTP and read in via IMAP
#

from optparse import OptionParser
from smtplib import SMTP, SMTP_SSL
from imaplib import IMAP4, IMAP4_SSL
import sys
import random
import string
import email
import time
import ldap

def smtp_send(user, passwd):
    if options.smtpssl:
        smtp = SMTP_SSL(options.smtp)
    else:
        smtp = SMTP(options.smtp)
        if options.smtptls:
            smtp.starttls()

    smtp.login(user, passwd)
    chars = string.letters + string.digits
    str_rand = "".join( [ random.choice(chars) for i in xrange(15) ] )
    subject = body = str_rand
    msg = "Subject: %s\n\r\n\r%s\n\r" % (subject, body)
    smtp.sendmail(user, user, msg)

    return subject

def imap_read(subject, user, passwd):
    if options.imapssl:
        imap = IMAP4_SSL(options.imap)
    else:
        imap = IMAP4(options.imap)

    resp = imap.login(user, passwd)
    if resp[0] != 'OK':
        print "%s imap auth failed." % (user)
        return

    imap.select()
    for i in range(0, int(options.fetchretries)):
        msgs = imap.search(None, 'SUBJECT', '"%s"' % (subject))
        for msgnum in msgs[1][0].split():
            msg = imap.fetch(msgnum, '(RFC822)')
            msg = msg[1][0][1]
            msg = email.message_from_string(msg)
            if msg['Subject'] == subject:
                return True
        time.sleep(int(options.fetchwait))

    return False

def ldap_test(user, passwd):
    l = ldap.initialize(options.ldapuri)

    user_bind = user.split('@')
    user_bind = 'uid=%s,%s' % (user_bind[0], options.ldapsuffix)
    l.bind(user_bind, passwd)

    filter = '(mail=%s)' % user
    r = l.search_s(options.ldapbase, ldap.SCOPE_SUBTREE, filter)

    if len(r):
        return True
    
    return False


usage = "usage: %s [options] -f file -s smtp -i imap" % (sys.argv[0])
parser = OptionParser(usage)

parser.add_option("-f", "--file", dest = "userlist",
                    help = "Read user and pass from FILE")

parser.add_option("-a", "--smtpauth", action = "store_true", dest = "smtpauth",
                    help = "Use SMTP authentication")

parser.add_option("-s", "--smtp", dest = "smtp",
                    help = "SMTP server")

parser.add_option("-i", "--imap", dest = "imap",
                    help = "IMAP server")

parser.add_option("--smtpssl", action = "store_true", dest = "smtpssl",
                    help = "Use SMTP SSL.")

parser.add_option("--smtptls", action = "store_true", dest = "smtptls",
                    help = "Use SMTP TLS.")

parser.add_option("--imapssl", action = "store_true", dest = "imapssl",
                    help = "Use IMAP SSL.")

parser.add_option("--fetch-retries", default = '1', dest = "fetchretries",
                    help = "Number of fetch retries.")

parser.add_option("--fetch-wait", default = '0', dest = "fetchwait",
                    help = "Seconds between retries.")

parser.add_option("--ldap-uri", dest = "ldapuri",
                    help = "LDAP server.")

parser.add_option("--ldap-base", dest = "ldapbase",
                    help = "LDAP base.")

parser.add_option("--ldap-suffix", dest = "ldapsuffix",
                    help = "LDAP suffix.")

(options, args) = parser.parse_args()

if not options.imap:
    parser.error("IMAP server is required.")

if not options.smtp:
    parser.error("IMAP server is required.")

if not options.userlist:
    parser.error("User and password list is requiered.")

if not options.fetchwait.isdigit():
    parser.error("--fetch-wait requires a number (seconds).")

if not options.fetchretries.isdigit():
    parser.error("--fetch-retries requires a number.")

userlist = open(options.userlist)
for userpw in userlist:
    userpw = userpw.strip()
    subject = smtp_send(*userpw.split())
    time.sleep(2)
    print userpw, subject,
    if imap_read(subject, *userpw.split()):
        print 'MAIL=OK',
    else:
        print 'MAIL=FAIL',

    if ldap_test(*userpw.split()):
        print 'LDAP=OK'
    else:
        print 'LDAP=FAIL'

