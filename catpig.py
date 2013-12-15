#!/usr/bin/python

import cups, sys, argparse, tempfile, string
from glob import glob
from urllib2 import urlopen


def pretty_string(message):
    "Make printer status messages a little tidier-looking."
    message = str(message)
    try:
        most, last = message.rsplit("-", 1)
        if last in ["warning", "report"]:
            message = most
    except ValueError:
        pass
    return message.translate(string.maketrans("-", " ")).title()


def display_job(job_id):
    "Print information about a job."
    job_attrs = job_list[job_id]
    status = pretty_string(job_attrs['job-state-reasons'][4:])
    if 'job-printer-state-message' in job_attrs:
        status = " -- {} ({})".format(status, job_attrs['job-printer-state-message'])
    user = job_attrs['job-originating-user-name']
    name = job_attrs['job-name']
    print "{}  {} ({}){}".format(str(job_id), name, user, status)


def print_details(printer_name):
    "Print detailed information about a printer's status, including jobs."
    print "Printer Name:\t{}".format(printer_name)
    try:
        printer = all_printers[printer_name]
    except KeyError:
        print "Location:\tNOT FOUND\n"
        return
    print "Location:\t{}".format(printer['printer-location'])
    print "Model:\t\t{}".format(printer['printer-make-and-model'])

    if 'printer-state-message' in printer and printer['printer-state-message']:
        print "Status:\t\t{}".format(printer['printer-state-message'])
    if printer['printer-state-reasons'][0] != "none":
        print "Messages:\t{}".format(pretty_string(printer['printer-state-reasons'].pop()))
        for reason in printer['printer-state-reasons']:
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

    if printer['printer-state-reasons'][0] != "none":
        alert = "!"
    else:
        alert = " "
    if len(jobs_by_printer[printer_name]):
        queue = "j"
    else:
        queue = " "
    prefix = queue + alert

    if args.alerts:
        info = ", ".join([pretty_string(r) for r in printer['printer-state-reasons']])
    else:
        info = printer['printer-location']

    print prefix, printer_name, "\t", info

    if args.jobs:
        for job_id in jobs_by_printer[printer_name]:
            print "   .",
            display_job(job_id)


def test_printer(printer_name):
    "Send a test page to the printer, after confirming."
    confirmations = ['y', 'yes']
    confirm = raw_input("Sending test page to {}. Confirm? ".format(printer_name))
    if confirm in confirmations:
        print "Fetching test page data ..."
        animal = urlopen('http://www.lorempixel.com/800/600/animals').read()
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
test prints. To add printers to catpig's checklist, list their names in files
whose names end in '.printers'.
""")
parser.add_argument("printer", metavar="PRINTER", nargs="?", help="substring of printer name(s) to get details on (if absent, catpig will print a summary)")
parser.add_argument("-a", "--alerts", action='store_true', help="show only the matching printers which have alerts")
parser.add_argument("-d", "--details", action='store_true', help="show details for all matching printers")
parser.add_argument("-j", "--jobs", action='store_true', help="list incomplete print jobs for matching printers")
parser.add_argument("-t", "--test", action='store_true', help="send a test to the selected printers, after confirming")
args = parser.parse_args()


# Connect to cups and get job and printer information.
conn = cups.Connection()
all_printers = conn.getPrinters()
jobs = conn.getJobs()

# Open *.printers files and build printer name lists.
check_printers = []
printers_by_file = {}
printer_lists = [p[2:] for p in glob("./*.printers")]
for list_file in printer_lists:
    with open(list_file) as fp:
        printers_by_file[list_file] = [p.strip() for p in fp.readlines()]
        check_printers.extend(printers_by_file[list_file])

# Filter by printer name string argument, if provided.
if args.printer:
    matched_printers = []
    test_name = args.printer.lower()
    matched_printers = [n for n in check_printers if test_name in n.lower()]
    if not matched_printers:
        print "No printers found matching {}. Run catpig with no arguments to get a list of printers.".format(args.printer)
        sys.exit(1)
else:
    matched_printers = check_printers

# Initialize job lists.
job_list = {}
jobs_by_printer = {}
for printer in all_printers:
    jobs_by_printer[printer] = []

# Get job information and sort by printer.
if jobs:
    for job_id in jobs:
        job = conn.getJobAttributes(job_id)
        printer = job['printer-uri'].rsplit('/', 1)[1]
        if args.printer and printer not in matched_printers:
            continue
        job_list[job_id] = conn.getJobAttributes(job_id)
        job_list[job_id]['printer'] = printer
        jobs_by_printer[printer].append(job_id)

# Filter for printers with alerts or jobs, if requested.
if args.jobs and args.alerts:
    matched_printers = [p for p in matched_printers if (p in jobs_by_printer and jobs_by_printer[p]) or (p in all_printers and all_printers[p]['printer-state-reasons'][0] != "none")]
elif args.jobs:
    matched_printers = [p for p in matched_printers if p in jobs_by_printer and jobs_by_printer[p]]
elif args.alerts:
    matched_printers = [p for p in matched_printers if p in all_printers and all_printers[p]['printer-state-reasons'][0] != "none"]


# Display requested information for matching printers.
for printer_name in matched_printers:
    if args.details:
        print_details(printer_name)
    else:
        print_summary(printer_name)
    if args.test:
        test_printer(printer_name)
