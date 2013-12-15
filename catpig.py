#!/usr/bin/python

import cups, argparse, tempfile, os, sys
from glob import glob
from urllib2 import urlopen
from string import maketrans


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

    if args.jobs:
        for job_id in jobs_by_printer[printer_name]:
            print "   .",
            display_job(job_id)


def test_printer(printer_name):
    "Send a test page to the printer, after confirming."
    confirmations = ["y", "yes"]
    confirm_query = "Sending test page to {}. Confirm? "
    confirm = raw_input(confirm_query.format(printer_name))
    if confirm in confirmations:
        print "Fetching test page data ..."
        animal = urlopen("http://www.lorempixel.com/800/600/animals").read()
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(animal)
            print "Fetched. Printing ..."
            conn.printFile(printer_name, fp.name, "CATPIG Test", {})
        print "Done."
    else:
        print "Aborted."


# Define command line options and help output.
parser = argparse.ArgumentParser(description="""
CAT Printer Information Generator. Get status of printers and jobs and send
test prints.
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
    help="send a test to the selected printers, after confirming")
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
    basedir = os.path.join(os.path.expanduser("~"), ".catpig/")
    printer_lists = glob(os.path.join(basedir, "*.printers"))
    if printer_lists:
        for list_file in printer_lists:
            with open(list_file) as fp:
                matched_printers.extend([p.strip() for p in fp.readlines()])
    else:
        sys.stderr.write("<!> No printer list found, using list from cups.\n\n")
        matched_printers = all_printers

# Filter by printer name string arguments, if provided.
if args.printer:
    filtered = []
    printer_patterns = map(lambda s: s.lower(), args.printer)
    for m in matched_printers:
        m = m.lower()
        for p in printer_patterns:
            if p in m:
                filtered.append(m)
                break
    matched_printers = filtered
    if not matched_printers:
        quoted_patterns = ["'{}'".format(p) for p in args.printer]
        pattern_string = " or ".join(quoted_patterns)
        print("No printers found matching {}.".format(pattern_string))
        if not args.cups and printer_lists:
            print "Checked {}".format(", ".join(printer_lists))

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
if args.jobs or args.alerts:
    filtered = []
    for p in matched_printers:
        if args.jobs and p in jobs_by_printer and jobs_by_printer[p]:
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
