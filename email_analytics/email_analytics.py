from imapclient import IMAPClient, SEEN, RECENT
from collections import defaultdict
import math
from email_reply_parser import EmailReplyParser
import email
from bs4 import BeautifulSoup, Comment
import pandas as pd
from datetime import datetime
import sys
import pickle
import multiprocessing as mp
import numpy as np
from afinn import Afinn



def connect_imap(host, port, admin_user, admin_pass, user=None, authenticate=False, ssl=True):
    
    imap = IMAPClient(host=host, port=port, ssl=ssl)
    
    if authenticate:
        imap.plain_login(identity=admin_user, password=admin_pass, authorization_identity=user)
    else:
        imap.login(username=admin_user, password=admin_pass)
    
    return imap



def get_id(imap, folder="INBOX", criteria=["ALL"], log_out=False):
    
    imap.select_folder(folder=folder) 
    uid_list = imap.search(criteria=criteria)
    
    if log_out:
        imap.logout()
    
    return uid_list



def fetch_email(imap, uid_list, start=None, end=None, fetch_data=["ENVELOPE", "RFC822"], keep_unseen=True, log_out=False):
    
    if start is None:
        start = 0
    if end is None:
        end = len(uid_list)
    uid_list = uid_list[start:end]
    
    if keep_unseen:
        flags = imap.get_flags(uid_list)
        unseen_uid = [uid for uid in flags.keys() if SEEN not in flags[uid]]
        data = imap.fetch(uid_list, data=fetch_data)
        imap.remove_flags(unseen_uid, SEEN, silent=True)
    else:
        data = imap.fetch(uid_list, data=fetch_data)
    
    if log_out:
        resp = imap.logout()
    
    return data



def parse_body(raw_message):
    """ Decode email body.
    Detect character set if the header is not set.
    We try to get text/plain, but if there is not one then fallback to text/html.
    :param message_body: Raw 7-bit message body input e.g. from imaplib. Double encoded in quoted-printable and latin-1
    :return: Message body as unicode string
    """
    if type(raw_message)==bytes:
        msg = email.message_from_bytes(raw_message)
    elif type(raw_message)==str:
        msg = email.message_from_string(raw_message)
        
    def parse_each_part(part):
        charset = part.get_content_charset()
            
        if part.get_content_type() == 'text/plain':
            text = part.get_payload(decode=True)
            if charset is not None:
                text = text.decode(encoding=charset)
            else:
                try:
                    text = text.decode(encoding="utf_8")
                except UnicodeDecodeError:
                    text = text.decode(encoding="'cp1250'")
            
            soup = BeautifulSoup(text, "lxml")
            if soup.body is not None:
                while soup.body.style is not None:
                    soup.body.style.decompose()
                while soup.body.pre is not None:
                    soup.body.pre.decompose()
                text = soup.body.get_text()
                
        elif part.get_content_type() == 'text/html':
            html_text = part.get_payload(decode=True)
         #   if charset is not None:
         #       html_text = html_text.decode(encoding=charset)
            soup = BeautifulSoup(html_text, "lxml")
            while soup.body.style is not None:
                soup.body.style.decompose()
            while soup.body.pre is not None:
                soup.body.pre.decompose()
            text = soup.body.get_text()
        else:
            text = ""
         #   html = str(part.get_payload(decode=True), charset, "ignore").encode('utf8', 'replace')
        return text
        
    text_list = []
    if msg.is_multipart():
        for i, part in enumerate(msg.walk()):
            #  print("%s, %s" % (part.get_content_type(), part.get_content_charset()))
            text = parse_each_part(part)    
            text_list.append(text)
    else:
        text_list.append(parse_each_part(msg))
            
    return "".join(text_list)



def search_domain(envelope_data, uid, domain_list):
    
    if envelope_data[uid]=={}:
        return False
    addresses = envelope_data[uid][b"ENVELOPE"].from_
    if addresses is None:
        return False
    bool_list = []
    for address in addresses:
        bool_list.append(address.host.decode() in domain_list)
    return (True in bool_list)



def parse_email(email_data, uid_list):
    
    email_dict_list = []
    
    for uid in uid_list:
        envelope = email_data[uid][b"ENVELOPE"]
        raw_message = email_data[uid][b"RFC822"]
        body_text = parse_body(raw_message)
        email_dict_list.append(dict(Date=envelope.date, From=envelope.from_, To=envelope.to, 
                                    Subject=envelope.subject.decode("utf-8"), Body=body_text))
    return dict(zip(uid_list, email_dict_list))



def parse_envelope(data, uid):
    
    envelope = data[uid][b"ENVELOPE"]
    
    return dict(Date=envelope.date, 
                From=envelope.from_,
                To=envelope.to,
                Subject=envelope.subject.decode("utf-8"))



def childprocess_fetch(uid_sublist, folder="INBOX", keep_unseen=True, log_out=True):
    
    imap = connect_imap(host, port, admin_user, admin_pass, user, authenticate=True)  ### Using predefined global variables here.
    imap.select_folder(folder=folder)
    
    if keep_unseen:
        flags = imap.get_flags(uid_sublist)
        unseen_uid = [uid for uid in flags.keys() if SEEN not in flags[uid]]
        data = imap.fetch(uid_sublist, data=child_fetch_data)                     ### fetch_data is predefined global variable
        imap.remove_flags(unseen_uid, SEEN, silent=True)
    else:
        data = imap.fetch(uid_sublist, data=fetch_data)
    
    if log_out:
        resp = imap.logout()
    
    return data



def mp_fetch(uid_list, num_workers):
    
    num_iter = math.ceil(len(uid_list) / 1000 / num_workers)
    num_partition = num_iter * num_workers
    list_uid_subarrays = np.array_split(uid_list, num_partition)
    list_uid_sublists = [uid_subarray.tolist() for uid_subarray in list_uid_subarrays]
    
    list_email_data = []
    
    for j in range(num_iter):
        
        start = j * num_workers
        end = (j+1) * num_workers
        pool = mp.Pool(num_workers)
        try:
            list_email_data += pool.map(childprocess_fetch, list_uid_sublists[start:end])
            print('Active children count: %d ' %len(mp.active_children()))
        finally:
            pool.close()
            pool.join()
        
    email_data = defaultdict()
    for sub_dict in list_email_data:
        email_data.update(sub_dict)
        
    return email_data



def scan(df_emails, print_col="Body", extra_print_col=None):
    
    for i, uid in enumerate(df_emails.index):
        print(df_emails.loc[uid, print_col])
        if extra_print_col is not None:
            extra = str(df_emails.loc[uid, extra_print_col])
        else:
            extra = ""
        s = input(str(uid) + "\n" + str(i) + "\n" + extra + "\n\n")
        if s=="break":
            break