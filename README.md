# email_analytics
This is a small Python package for the tasks to extract emails from the host server, parse the unstructured encoding raw text to human readable email text, and organize them into structured DataFrame combined with other metadata.

You could run \
```git clone git@github.com:JiachengHe/email_analytics.git``` \
and run \
```python email_analytics/setup.py install``` \
to install the package.

## Fetching user emails via an admnistrative account
Suppose a corporate organization is interested to analyze employees' business email exchanges with clients, and gain insights from the daily communication. We could ask the domain adminstrator to set up an adminstrative account with access to those users of interest. Then we can use this package to log into the administrative account, authenticate the employees' user address, and fetch those emails. Only the password of the administrative account is required.

Below is a sample script to extract all emails from a user's inbox:
```python
from email_analytics import *

host = "outlook.office365.com"
port = 993
admin_user = "admin_address@domain_name.com"
admin_pass = "123456789"
user = "user_address@domain_name.com"

with connect_imap(host, port, admin_user, admin_pass, user, authenticate=True, ssl=True) as imap:
    uid_list = get_id(imap, folder="INBOX", criteria=["ALL"])
    all_email_data = fetch_email(imap, uid_list, fetch_data=["ENVELOPE", "RCF822"], keep_unseen=True)
```
This package uses [IMAPClient](https://imapclient.readthedocs.io/en/master/) as backend. Please refer to their [documents](https://imapclient.readthedocs.io/en/master/api.html#fetch-response-types) about the fetch_data types. In summary, "ENVELOPE" contains the metadata and "RCF822" contains the email raw text.

Setting ```keep_unseen=True``` so that our administrative behavior does not remove the unseen flag of users' unseen emails.

## Narrow down clients' domain names
Suppose we are only interested in the inbox emails coming from a specific group of clients
```python
client_domain_list = ["client_1.com", "client_2.edu", "client_3.com", "client_4.gov"]

with connect_imap(host, port, admin_user, admin_pass, user, authenticate=True, ssl=True) as imap:
    uid_list = get_id(imap, folder="INBOX", criteria=["ALL"])
    envelope_data = fetch_email(imap, uid_list, fetch_data=["RCF822"], keep_unseen=True)
    client_uid_list = [uid for uid in uid_list if search_domain(envelope_data, uid, client_domain_list)]
    client_email_data = fetch_email(imap, uid_list, fetch_data=["ENVELOPE", "RCF822"], keep_unseen=True)
```

## Email parser
To parse the encoding raw text, we can use the ```parse_email``` function, which returns a Python dictionary with UIDs as keys:
```python
client_email_dict = parse_email(client_email_data, client_uid_list)
```
the ```client_uid_list``` provides which UIDs to parse.

## Create a DataFrame
Then we can construct a Pandas DataFrame:
```python
import pandas as pd
df_emails = pd.DataFrame.from_dict(client_email_dict, orient="index")
```

## Run the download jobs in parallel
When there is a huge volume of users, clients, and emails needed to be extracted, running the download tasks in parallel can save our time. This package provides a ```mp_fetch``` function to create multiple processes to run the fetching jobs.
```python
import multiprocessing as mp
num_workers = mp.cpu_count()

### Because to share one SSL context with multiple processes is not supported.
### So for each process, we have to create a distinct SSL context inside that process
### This is achieved by calling global variables
host = "outlook.office365.com"
port = 993
admin_user = "admin_address@domain_name.com"
admin_pass = "123456789"
user = "user_address@domain_name.com"
child_fetch_data = ["ENVELOPE", "RFC822"]

email_data = mp_fetch(uid_list, num_workers)
```
