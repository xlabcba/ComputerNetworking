# Web Crawler

## High Level Approach:

Our crawler works in asynchronous fashion and crawl by DFS traversal.
It consists of a main crawler and hundreds of workers to implement the asynchronous fashion. Master Crawler maintains a set of found flags, a set as DFS stack of url paths to visit, and a set of url paths which have been visited. It executes event loop to select I/O-ready workers, assign tasks, and update result workers into corresponding lists. A Master Crawler has hundreds of workers. Each has connection with server and is in charge of I/O from socket and parse page after read task is done to return to Master Crawler.

### Master crawler

Master crawler works as following:

* Login:

1. First GET to get the login page.
2. First POST to login fakebook account, and records the first location to visit and the cookies for the following requests.

* Asynchronous Crawling Until 5 Flags All Founded:

1. Select readable and writable workers list by using select() system call.
2. Iterate readable and writable workers list separately
3. Assign new task to idle workers.
4. Merges the result from worker into the corresponding list.

### Worker

Each worker wraps a non-blocking socket, and works in one of the following state:

```
0 - write mode;  1 - read mode;  -1 - error mode;
```

Worker runs in following mechanism:

1. Initialized in write mode, and wait for writing job from Master Crawler.
2. Assigned writing job from Master Crawler, and keep working on it.
3. After finish writing, switch to read mode to read the response page.
4. After finish reading, analyze the response, and return result to Master Crawler.
5. Reset to initial state and repeat step 1 to 4.

## Challenge:
1. Need two separate socket connections for going to the fakebook login page and actually log in. We originally had only one socket, so we always fail at log in step.
2. It was difficult to come to the understanding that we cannot send and recv all data at once. Instead, we have to concatenate the data we send and recv each time to get the full data.
3. Use non-blocking sockets to transmit data and select readable/writable list to improve efficiency.
4. Understand the differences among HTTP status codes and categorize the ones that have the same functionalities.
5. Detect if the socket has received all the data in the worker (i.e. the html page that has been crawled).

## Code Testing:
We have manually tested most methods in each class separately against http://cs5700f16.ccs.neu.edu/. For methods that are more tricky to test, we have run them many times with print statements to verify the results we get are the ones expected.

Makefile is intentionally left empty

## Verbose Information

### Response for login page:
```
HTTP/1.1 200 OK
Date: Sun, 02 Oct 2016 00:10:01 GMT
Server: Apache/2.2.22 (Ubuntu)
Content-Language: en-us
Expires: Sun, 02 Oct 2016 00:10:01 GMT
Vary: Cookie,Accept-Language,Accept-Encoding
Cache-Control: max-age=0
Set-Cookie: csrftoken=2a492b5fb6f08688992f70593522a0db; expires=Sun, 01-Oct-2017 00:10:01 GMT; Max-Age=31449600; Path=/
Set-Cookie: sessionid=19cd6b8aca092c99c4da1b8d3c5fc2d3; expires=Sun, 16-Oct-2016 00:10:01 GMT; Max-Age=1209600; Path=/
Last-Modified: Sun, 02 Oct 2016 00:10:01 GMT
Content-Length: 1142
Content-Type: text/html; charset=utf-8


<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">

<head>
    <title>Fakebook</title>
</head>

<body>
    <div id="header">

	<a href="/">Home</a> |


	<a href="/accounts/login/">Log in</a>

	<hr />

    </div>

    <div id="content">

<form method="post" action=".">
  <p><label for="id_username">Username:</label> <input id="id_username" type="text" name="username" maxlength="30" /></p>
<p><label for="id_password">Password:</label> <input id="id_password" type="password" name="password" maxlength="4096" /></p>
<div style='display:none'><input type='hidden' name='csrfmiddlewaretoken' value='2a492b5fb6f08688992f70593522a0db' /></div>
  <input type="submit" value="Log in" />
  <input type="hidden" name="next" value="" />
</form>

<p>Forgot password? <a href="/accounts/password/reset/">Reset it</a>!</p>
<p>Not member? <a href="/accounts/register/">Register</a>!</p>

    </div>

    <div id="footer">

        <hr />

    </div>
</body>

</html>
```

### Response after login:
```
HTTP/1.1 302 FOUND
Date: Sat, 01 Oct 2016 23:12:16 GMT
Server: Apache/2.2.22 (Ubuntu)
Content-Language: en-us
Expires: Sat, 01 Oct 2016 23:12:16 GMT
Vary: Accept-Language,Cookie,Accept-Encoding
Cache-Control: max-age=0
Set-Cookie: sessionid=24f7f54a938aa959ee6970d42f47d8f3; expires=Sat, 15-Oct-2016 23:12:16 GMT; Max-Age=1209600; Path=/
Last-Modified: Sat, 01 Oct 2016 23:12:16 GMT
Location: http://cs5700f16.ccs.neu.edu/fakebook/
Content-Length: 0
Content-Type: text/html; charset=utf-8
```