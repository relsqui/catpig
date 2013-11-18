#!/usr/bin/python

import cups, sys, argparse, tempfile, string
from pprint import pprint
from glob import glob
from urllib2 import urlopen


conn = cups.Connection()
all_printers = conn.getPrinters()

check_printers = []
printers_by_file = {}
printer_lists = [p[2:] for p in glob("./*.printers")]
for list_file in printer_lists:
    with open(list_file) as fp:
        printers_by_file[list_file] = [p.strip() for p in fp.readlines()]
        check_printers.extend(printers_by_file[list_file])

jobs = conn.getJobs()
job_list = {}
jobs_by_printer = {}
for printer in all_printers:
    jobs_by_printer[printer] = []

if jobs:
    for job_id in jobs:
        job_list[job_id] = conn.getJobAttributes(job_id)
        printer = job_list[job_id]['printer-uri'].rsplit('/', 1)[1]
        job_list[job_id]['printer'] = printer
        jobs_by_printer[printer].append(job_id)

def pretty_string(message):
    # casting to string to ensure non-unicode
    return str(message).translate(string.maketrans("-", " ")).title()

def print_job(job_id, show_printer=True):
    job_attrs = job_list[job_id]
    status = pretty_string(job_attrs['job-state-reasons'][4:])
    user = job_attrs['job-originating-user-name'].ljust(9)
    name = job_attrs['job-name'].ljust(9)
    message = job_attrs['job-printer-state-message']
    if show_printer:
        printer = job_attrs['printer']
        print "\t".join([str(job_id), printer, user, name, status, message])
    else:
        print "\t".join([str(job_id), user, name, status, message])


parser = argparse.ArgumentParser(description="""
CAT Printer Information Generator. Get information on available printers
and send test prints. To add printers to catpig's checklist, list their IDs
in files whose names end in '.printers'.  The IDs will be grouped by file
in the summary view.
""")
parser.add_argument("printer", metavar="PRINTER", choices=check_printers, nargs="?", help="ID of printer (if absent, catpig will print a summary)")
parser.add_argument("-a", "--alerts", action='store_true', help="summarize only the printers which have alerts")
parser.add_argument("-j", "--jobs", action='store_true', help="list any incomplete print jobs")
parser.add_argument("-t", "--test", action='store_true', help="send a test page to the selected printer, after confirming")
args = parser.parse_args()


if args.printer:
    try:
        printer = all_printers[args.printer]
    except KeyError:
        print "Sorry, I don't know of a printer called {}. Run catpig with no arguments to get a list of printers.".format(args.printer)
        sys.exit(1)
    print "Location:\t{}".format(printer['printer-location'])
    print "Model:\t\t{}".format(printer['printer-make-and-model'])
    if printer['printer-state-message']:
        print "Status:\t\t{}".format(printer['printer-state-message'])
    if printer['printer-state-reasons'][0] != "none":
        print "Messages:\t{}".format(pretty_string(printer['printer-state-reasons'].pop()))
        for reason in printer['printer-state-reasons']:
            print "\t\t{}".format(pretty_string(reason))
    if jobs_by_printer[args.printer]:
        print "Jobs:"
        for job_id in jobs_by_printer[args.printer]:
            print "\t",
            print_job(job_id, show_printer=False)
    if args.test:
        confirmations = ['y', 'yes']
        print
        confirm = raw_input("Sending test page. Confirm? ")
        if confirm in confirmations:
            print "Confirmed. Fetching test page data ..."
            animal = urlopen('http://www.lorempixel.com/800/600/animals').read()
            with tempfile.NamedTemporaryFile() as fp:
                tempfilename = fp.name
                fp.write(animal)
                print "Fetched. Printing ..."
                conn.printFile(args.printer, tempfilename, "CATPIG Test", {})
            print "Done."
        else:
            print "Aborted."

elif args.jobs:
    for job_id in job_list:
        print_job(job_id)

else:
    for filename in printer_lists:
        status_list = []
        for printer_name in printers_by_file[filename]:
            if printer_name not in all_printers.keys():
                status_list.append("XX {}\tNOT FOUND".format(printer_name))
                continue
            printer = all_printers[printer_name]

            if printer['printer-state-reasons'][0] != "none":
                has_messages = True
                alert = "!"
            else:
                has_messages = False
                alert = " "

            if args.alerts:
                if not has_messages:
                    continue
                prefix = ""
                info = ", ".join(printer['printer-state-reasons'])
            else:
                if len(jobs_by_printer[printer_name]):
                    queue = "j"
                else:
                    queue = " "
                prefix = queue + alert + " "
                info = printer['printer-location']
            status_list.append("{}{}\t{}".format(prefix, printer_name, info))
        heading = " ".join(filename.split(".")).upper()
        if status_list:
            print heading
            print "\n".join(status_list)
            print
        elif not args.alerts:
            print heading
            print "   (no printers)"
            print
