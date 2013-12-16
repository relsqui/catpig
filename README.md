CATpig
======
is the CAT printer information generator. It can be used to create a quick summary on all the printers in a CUPS system, read status alerts, send test messages, and view or cancel incomplete print jobs.

### Installation and Files ###
The only file actually required to use CATpig is `catpig.py`. All the python modules it uses are built-in, so you can just drop it somewhere in your path and you're good to go. That said, CATpig will look for a directory called `~/.catpig` and can do some useful things if it finds the following in it (especially if you also have sendmail running):

 * `*.printers` - If any files matching this glob are present, CATpig will look in them for printer names and ignore all other printers. Useful if you're only managing a small part of a large CUPS system. (You can override this behavior with the `-c` command line switch.)
 * `config` - If present, this should contain headers and a message body filename with which to email users when their jobs are killed. See *Email* for more details.

### Quick Reference ###
```
usage: catpig [-h] [-a] [-j] [-v] [-t] [-k] [-c] [PRINTER [PRINTER ...]]

CAT Printer Information Generator. Get status of printers whose names match
all the substrings provided (if any are), either from lists given in
~/.catpig/*.printers or directly from cups; send test pages; manage jobs.

positional arguments:
  PRINTER        substrings of printer names to look for

optional arguments:
  -h, --help     show this help message and exit
  -a, --alerts   show printers which have alerts, and list them
  -j, --jobs     show printers which have unfinished jobs, and list them
  -v, --verbose  show detailed information for the selected printers
  -t, --test     prompt to send a test to selected printers
  -k, --kill     prompt to kill listed unfinished jobs; implies -j
  -c, --cups     use printer list from cups instead of ~/.catpig/*.printers
```

### Basic Usage ###
Once your configuration is set up (if desired), you can get a summary view of all your printers by just running `catpig`.

```
[jschmoe@it ~]$ catpig
 ! frontdesk    Reception Counter
   office1      Alice's Office
   office2bw    Conference Room
j! office2clr   Conference Room
   office3      Bob's Office
```

To see just the printers with alerts, use the `-a` switch. This will show the content of the alerts instead of the printer location.

```
[jschmoe@it ~]$ catpig -a
 ! frontdesk    Toner Empty, Media Low
j! office2clr   Media Jam
```

`-j` shows only printers with jobs in queue; `-aj` shows printers that have alerts, jobs, or both, i.e. printers that are likely to need your attention.

```
[jschmoe@it ~]$ catpig -aj
 ! frontdesk    Toner Empty, Media Low
j! office2clr   Media Jam
   . 6803  important_report.pdf (alice)
   . 6804  complex_spreadsheet.xls (bob)
```

So the front desk printer needs toner and paper, and the color printer in the conference room is jammed. You happen to know that Alice and Bob have printed their documents elsewhere already, so you can kill these jobs with the `-k` switch.

```
[jschmoe@it ~]$ catpig -k
j! office2clr   Media Jam
   . 6803  important_report.pdf (alice)
Cancel job #6803? y
Job removed.
Send email? n
Aborted.
   . 6804  complex_spreadsheet.pdf (bob)
Cancel job #6804? y
Job removed.
Send email? n
Aborted.

[jschmoe@it ~]$ catpig -aj
 ! frontdesk    Toner Empty, Media Low
 ! office2clr   Media Jam
```

It's still jammed, but now there aren't jobs waiting to spew out as soon as you clear it.

### Additional Examples ###
Now you're out picking up toner for the front desk printer, but you've forgotten what the model is. Rather than calling the office and bugging someone to check, just ssh back to your workstation and use CATpig. You can pass a positional parameter to limit your view to the printers you're interested in ...

```
[jschmoe@it ~]$ catpig desk
 ! frontdesk    Toner Empty, Media Low
```

... and add the `-v` switch to show more information.

```
[jschmoe@it ~]$ catpig -v desk
Printer Name:   frontdesk
Location:       Reception Counter
Model:          HP LaserJet 4250 - CUPS+Gutenprint v5.2.8-pre1
Messages:       Toner Empty
                Media Low
```

Note that the parameter doesn't have to be the full printer name, just any substring. You can pass more than one parameter to see all the printers which match *all* of them. This is useful if you know one of the offices has a color printer but don't remember which one (or the printer naming scheme).

```
[jschmoe@it ~]$ catpig off clr
 ! office2clr   Media Jam
```

After installing the new toner, it's a good idea to do a test print and make sure it's running smoothly.

```
[jschmoe@it ~]$ catpig -t desk
 ! frontdesk    Media Low
Sending test page to frontdesk. Confirm? y
Fetching test page data ...
Fetched. Printing ...
Done.
```

CATpig fetches its full-color test pages from the animals section of lorempixel.com, which provides random filler images specified by size and category. If you leave off the filtering positional parameters, get the full printer list from cups, and automate the confirmations (i.e. `yes | catpig -ct`) you can automatically send random animal photos to every printer in the office. Just saying.

### Email ###
To have CATpig email users when you kill their jobs, you need to have two things in your `~/.catpig`: a configuration file, and a text file that contains the body of the email. Examples of both are included in `example.catpig`. You will also need sendmail running.

Only four of the configuration options are absolutely required for email to work: `To`, `From`, and `Subject` (in the headers section), and `body` (in the body section). Any extra variables in the headers section will be appended to the email headers. The body section can also contain a `signature` variable giving the name of a signature file.

The email header values, as well as the body and signature files, can (and should!) contain variables in braces, which Python will replace with the appropriate values for the given job. There are four available:

 * `{user}` becomes the username which sent the print job.
 * `{me}` becomes the username which is running CATpig.
 * `{name}` becomes the filename of the job.
 * `{printer}` becomes the name of the printer the job was on.

Therefore, if we had sent out email for the jobs we killed above, using the example configuration, one of them might have looked like this:

```
Content-Type: text/plain; charset="us-ascii"
Content-Transfer-Encoding: 7bit
To: alice@ouroffice.example.com
Subject: Your print job(s) on office2clr have been removed.
From: jschmoe@support.example.com
Date: Monday, 16 Dec 2013 09:00:14 -0800 (PST)

Dear alice,

Your job, important_report.pdf, on office2clr, was cancelled by jschmoe.
Have a nice day!

---
Joe Schmoe
Generic Office IT
support@ouroffice.example.com
(510) 555-1234
```
