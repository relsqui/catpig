#!/usr/bin/python

import cups, argparse, tempfile, os, sys, smtplib, pwd, ConfigParser
from glob import glob
from urllib2 import urlopen
from string import maketrans
from email.mime.text import MIMEText


confirmations = ["y", "yes"]
basedir = os.path.join(os.path.expanduser("~"), ".catpig/")


def print_error(message):
    sys.stderr.write("{}\n".format(message))

def pretty_string(message):
    "Make printer status messages a little tidier-looking."
    message = str(message)
    try:
        most, last = message.rsplit("-", 1)
        if last in ["warning", "report"]:
            message = most
    except ValueError:
        pass
    return message.translate(maketrans("-", " ")).title()


def display_job(job_id):
    "Print information about a job."
    job_attrs = job_list[job_id]
    status = pretty_string(job_attrs["job-state-reasons"][4:])
    if "job-printer-state-message" in job_attrs:
        message = job_attrs["job-printer-state-message"]
        status = " -- {} ({})".format(status, message)
    user = job_attrs["job-originating-user-name"]
    name = job_attrs["job-name"]
    print "{}  {} ({}){}".format(str(job_id), name, user, status)


def print_details(printer_name):
    "Print detailed information about a printer's status, including jobs."
    print "Printer Name:\t{}".format(printer_name)
    try:
        printer = all_printers[printer_name]
    except KeyError:
        print "Location:\tNOT FOUND\n"
        return
    print "Location:\t{}".format(printer["printer-location"])
    print "Model:\t\t{}".format(printer["printer-make-and-model"])

    if "printer-state-message" in printer and printer["printer-state-message"]:
        print "Status:\t\t{}".format(printer["printer-state-message"])
    if printer["printer-state-reasons"][0] != "none":
        first_message = printer["printer-state-reasons"].pop()
        print "Messages:\t{}".format(pretty_string(first_message))
        for reason in printer["printer-state-reasons"]:
            print "\t\t{}".format(pretty_string(reason))

    if jobs_by_printer[printer_name]:
        print "Jobs:\t\t",
        display_job(jobs_by_printer[printer_name][0])
        for job_id in jobs_by_printer[printer_name][1:]:
            print "\t\t",
            display_job(job_id)
    print


def print_summary(printer_name):
    "Print a one-line summary of printer status."
    try:
        printer = all_printers[printer_name]
    except KeyError:
        print "XX {}\tNOT FOUND".format(printer_name)
        return

    if printer["printer-state-reasons"][0] != "none":
        alert = "!"
    else:
        alert = " "
    if len(jobs_by_printer[printer_name]):
        queue = "j"
    else:
        queue = " "
    prefix = queue + alert

    if args.alerts:
        alerts = [pretty_string(r) for r in printer["printer-state-reasons"]]
        info = ", ".join(alerts)
    else:
        info = printer["printer-location"]

    print prefix, printer_name, "\t", info

    if args.jobs or args.kill:
        for job_id in jobs_by_printer[printer_name]:
            print "   .",
            display_job(job_id)
            if not args.kill:
                continue

            confirm = raw_input("Cancel job #{}? ".format(job_id))
            if confirm not in confirmations:
                print_error("Aborted.")
                continue

            conn.cancelJob(job_id)
            print_error("Job removed.")

            confirm = raw_input("Send email? ")
            if confirm not in confirmations:
                print_error("Aborted.")
                continue

            job = job_list[job_id]
            email_vars = {
                "user": job["job-originating-user-name"],
                "me": pwd.getpwuid(os.getuid()).pw_name,
                "name": job["job-name"],
                "printer": printer_name
            }

            try:
                config_file = os.path.join(basedir, "config")
                with open(config_file) as fp:
                    config = ConfigParser.ConfigParser()
                    config.optionxform = str
                    config.readfp(fp)
            except IOError:
                print_error("Couldn't read config file: {}".format(config_file))
                continue

            try:
                body_file = os.path.join(basedir,
                                         config.get("Job Email Body", "body"))
                with open(os.path.join(basedir, body_file)) as fp:
                    body = fp.read()
            except KeyError:
                print_error("No message body filename found. (It should be in "
                            "the option 'body' and section 'Job Email Body'.)")
                continue
            except IOError:
                print_error("Couldn't read email body file: "
                            "{}".format(body_file))
                continue

            try:
                sig_file = os.path.join(basedir,
                                      config.get("Job Email Body", "signature"))
                with open(sig_file) as fp:
                    signature = fp.read()
                body += "\n" + signature
            except KeyError:
                print_error("(No signature filename found, continuing anyway.)")
            except IOError:
                print_error("Couldn't read signature file: {}".format(sig_file))
                continue

            body = body.format(**email_vars)

            headers = {}
            for header, value in config.items("Job Email Headers"):
                headers[header] = value.format(**email_vars)

            try:
                for req in ["To", "From", "Subject"]:
                    if req not in headers:
                        print_error("Missing required header: {}".format(req))
                        raise KeyError
            except KeyError:
                continue

            msg = MIMEText(body)
            for header, value in headers.items():
                msg[header] = value

            sender = headers["From"]
            try:
                receivers = [headers["To"]]
                receivers.append(headers["CC"])
                receivers.append(headers["BCC"])
            except KeyError:
                pass

            s = smtplib.SMTP('localhost')
            s.sendmail(sender, receivers, msg.as_string())
            s.quit()
            print_error("Sent.")

def test_printer(printer_name):
    "Send a test page to the printer, after confirming."
    confirm_query = "Sending test page to {}. Confirm? "
    confirm = raw_input(confirm_query.format(printer_name))
    if confirm in confirmations:
        print_error("Fetching test page data ...")
        animal = urlopen("http://www.lorempixel.com/800/600/animals").read()
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(animal)
            print_error("Fetched. Printing ...")
            conn.printFile(printer_name, fp.name, "CATPIG Test", {})
        print_error("Done.")
    else:
        print_error("Aborted.")


# Define command line options and help output.
parser = argparse.ArgumentParser(description="""
CAT Printer Information Generator. Get status of printers whose names match
all the substrings provided (if any are), either from lists given in
~/.catpig/*.printers or directly from cups.
""")
parser.add_argument("printer", metavar="PRINTER", nargs="*",
    help="substrings of printer names to look for")
parser.add_argument("-a", "--alerts", action="store_true",
    help="show printers which have alerts, and list them")
parser.add_argument("-j", "--jobs", action="store_true",
    help="show printers which have unfinished jobs, and list them")
parser.add_argument("-d", "--details", action="store_true",
    help="show detailed information for the selected printers")
parser.add_argument("-t", "--test", action="store_true",
    help="prompt to send a test to selected printers")
parser.add_argument("-k", "--kill", action="store_true",
    help="prompt to kill listed unfinished jobs; implies -j")
parser.add_argument("-c", "--cups", action="store_true",
    help="use printer list from cups instead of ~/.catpig/*.printers")
args = parser.parse_args()


# Connect to cups and get job and printer information.
conn = cups.Connection()
all_printers = conn.getPrinters()
jobs = conn.getJobs()

if args.cups:
    matched_printers = all_printers
else:
    # Open *.printers files and build printer name lists.
    matched_printers = []
    printer_lists = glob(os.path.join(basedir, "*.printers"))
    if printer_lists:
        for list_file in printer_lists:
            with open(list_file) as fp:
                matched_printers.extend([p.strip() for p in fp.readlines()])
    else:
        print_error("No printer list found, using list from cups.\n")
        matched_printers = all_printers

# Filter by printer name string arguments, if provided.
if args.printer:
    filtered = []
    printer_patterns = map(lambda s: s.lower(), args.printer)
    for m in matched_printers:
        m = m.lower()
        for p in printer_patterns:
            if p not in m:
                break
        else:
            filtered.append(m)
    matched_printers = filtered
    if not matched_printers:
        quoted_patterns = ["'{}'".format(p) for p in args.printer]
        pattern_string = " and ".join(quoted_patterns)
        print_error("No printers found matching {}.".format(pattern_string))
        if not args.cups and printer_lists:
            print_error("Checked {}".format(", ".join(printer_lists)))

# Initialize job lists.
job_list = {}
jobs_by_printer = {}
for printer in all_printers:
    jobs_by_printer[printer] = []

# Get job information and sort it by printer.
if jobs:
    for job_id in jobs:
        job = conn.getJobAttributes(job_id)
        printer = job["printer-uri"].rsplit("/", 1)[1]
        if printer not in matched_printers:
            continue
        job_list[job_id] = conn.getJobAttributes(job_id)
        job_list[job_id]["printer"] = printer
        jobs_by_printer[printer].append(job_id)

# Filter for printers with alerts or jobs, if requested.
if args.jobs or args.kill or args.alerts:
    filtered = []
    for p in matched_printers:
        if ((args.jobs or args.kill)
            and p in jobs_by_printer and jobs_by_printer[p]):
            filtered.append(p)
        elif (args.alerts and p in all_printers
              and all_printers[p]["printer-state-reasons"][0] != "none"):
            filtered.append(p)
    matched_printers = filtered

# Display requested information for matching printers.
for printer_name in matched_printers:
    if args.details:
        print_details(printer_name)
    else:
        print_summary(printer_name)
    if args.test:
        test_printer(printer_name)
