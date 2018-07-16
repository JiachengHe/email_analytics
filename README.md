# email_analytics
A Python package for extracting user emails via an administrative account.


Suppose the organization is using Office Outlook server and "domain_name" as their domain name. Here is a basic example of extracting all inbox emails in a particular user account:

```python
from email_analytics import *

host = "outlook.office365.com"
port = 993
admin_user = "admin_account@domain_name.com"
admin_pass = "xxooxo"
user = "user_account@domain_name.com"

with connect_imap(host, port, admin_user, admin_pass, user, authenticate=True, ssl=True) as imap:
    uid_list = get_id(imap, folder="INBOX", criteria=["ALL"])
    all_email_data = fetch_email(imap, uid_list, fetch_data=["ENVELOPE", "RCF822"], keep_unseen=True)
```
Setting ```keep_unseen=True``` so that our administrative behavior of extracting emails does not remove the unseen flag on the user's side.

Suppose we are only interested in the inbox emails from a specific group of clients
```python
client_domain_list = ["client_1.com", "client_2.edu", "client_3.com", "client_4.gov"]

with connect_imap(host, port, admin_user, admin_pass, user, authenticate=True, ssl=True) as imap:
    uid_list = get_id(imap, folder="INBOX", criteria=["ALL"])
    envelope_data = fetch_email(imap, uid_list, fetch_data=["RCF822"], keep_unseen=True)
    client_uid_list = [uid for uid in uid_list if search_domain(envelope_data, uid, client_domain_list)]
    client_email_data = fetch_email(imap, uid_list, fetch_data=["ENVELOPE", "RCF822"], keep_unseen=True)
```

To parse the email raw encoding texts, we can use the ```parse_email``` function, which returns a Python dictionary with UIDs as keys:
```python
client_email_dict = parse_email(client_email_data, client_uid_list)
```
or
```python
client_email_dict = parse_email(all_email_data, client_uid_list)
```
the ```client_uid_list``` provides which UIDs to parse.

Then we can construct a Pandas DataFrame:
```python
import pandas as pd
df_emails = pd.DataFrame.from_dict(client_email_dict, orient="index")
```

We can use ```mp_fetch``` function to create multiple processes to download emails from the server to accelerate the speed. 
```python
import multiprocessing as mp
num_workers = mp.cpu_count()

### We have to define these parameters as global variables. 
### Because to share one SSL context with multiple processes is not supported
host = "outlook.office365.com"
port = 993
admin_user = "admin_account@domain_name.com"
admin_pass = "xxooxo"
user = "user_account@domain_name.com"
child_fetch_data = ["ENVELOPE", "RFC822"]
###

email_data = mp_fetch(uid_list, num_workers)
```
