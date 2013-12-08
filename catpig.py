#!/usr/bin/python

import cups, sys, argparse, tempfile, string
from glob import glob
from urllib2 import urlopen


def pretty_string(message):
    message = str(message)
    try:
        most, last = message.rsplit("-", 1)
        if last in ["warning", "report"]:
            message = most
    except ValueError:
        pass
    return message.translate(string.maketrans("-", " ")).title()

def display_job(job_id, show_printer=True):
    job_attrs = job_list[job_id]
    status = pretty_string(job_attrs['job-state-reasons'][4:])
    if 'job-printer-state-message' in job_attrs:
        status = "{} ({})".format(status, job_attrs['job-printer-state-message'])
    user = job_attrs['job-originating-user-name'].ljust(9)
    name = job_attrs['job-name'].ljust(9)
    if show_printer:
        printer = job_attrs['printer']
        print "\t".join([str(job_id), printer, status, user, name])
    else:
        print "\t".join([str(job_id), status, user, name])

def test_printer(printer_name, ask_first = True):
    confirmations = ['y', 'yes']
    if ask_first:
        confirm = raw_input("Sending test page to {}. Confirm? ".format(printer_name))
    else:
        confirm = 'y'
    if confirm in confirmations:
        if ask_first:
            print "Confirmed. ",
        print "Fetching test page data ..."
        animal = urlopen('http://www.lorempixel.com/800/600/animals').read()
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(animal)
            print "Fetched. Printing ..."
            conn.printFile(printer_name, fp.name, "CATPIG Test", {})
        print "Done."
    else:
        print "Aborted."


parser = argparse.ArgumentParser(description="""
CAT Printer Information Generator. Get information on available printers
and send test prints. To add printers to catpig's checklist, list their names
in files whose names end in '.printers'.  The names will be grouped by file
in the summary view.
""")
parser.add_argument("printer", metavar="PRINTER", nargs="?", help="substring of printer name(s) to get details on (if absent, catpig will print a summary)")
parser.add_argument("-a", "--alerts", action='store_true', help="show only the printers which have alerts")
parser.add_argument("-d", "--details", action='store_true', help="show details for all matching printers")
parser.add_argument("-j", "--jobs", action='store_true', help="list incomplete print jobs instead of printers")
parser.add_argument("-t", "--test", action='store_true', help="send a test to the selected printers, after confirming")
args = parser.parse_args()
args_on = [v[0] for v in vars(args).items() if v[1]]


conn = cups.Connection()
all_printers = conn.getPrinters()
jobs = conn.getJobs()

check_printers = []
printers_by_file = {}
printer_lists = [p[2:] for p in glob("./*.printers")]
for list_file in printer_lists:
    with open(list_file) as fp:
        printers_by_file[list_file] = [p.strip() for p in fp.readlines()]
        check_printers.extend(printers_by_file[list_file])

matched_printers = []
if args.printer:
    test_name = args.printer.lower()
    matched_printers = [n for n in check_printers if test_name in n]
    if not matched_printers:
        print "No printers found matching {}. Run catpig with no arguments to get a list of printers.".format(args.printer)
        sys.exit(1)

if args.alerts:
    if not matched_printers:
        matched_printers = check_printers
    matched_printers = [p for p in matched_printers if p in all_printers and all_printers[p]['printer-state-reasons'][0] != "none"]

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


if args.details:
    if not matched_printers:
        matched_printers = check_printers
    for printer_name in matched_printers:
        printer = all_printers[printer_name]
        print "Printer Name:\t{}".format(printer_name)
        print "Location:\t{}".format(printer['printer-location'])
        print "Model:\t\t{}".format(printer['printer-make-and-model'])
        if 'printer-state-message' in printer:
            print "Status:\t\t{}".format(printer['printer-state-message'])
        if printer['printer-state-reasons'][0] != "none":
            print "Messages:\t{}".format(pretty_string(printer['printer-state-reasons'].pop()))
            for reason in printer['printer-state-reasons']:
                print "\t\t{}".format(pretty_string(reason))
        if jobs_by_printer[printer_name]:
            print "Jobs:"
            for job_id in jobs_by_printer[printer_name]:
                print "\t",
                display_job(job_id, show_printer=False)
        if args.test:
            test_printer(printer_name)
        print


elif args.alerts or not args_on:
    listed_printers = []
    for filename in printer_lists:
        status_list = []
        for printer_name in printers_by_file[filename]:
            if matched_printers and printer_name not in matched_printers:
                continue

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
                info = ", ".join([pretty_string(r) for r in printer['printer-state-reasons']])
            else:
                if len(jobs_by_printer[printer_name]):
                    queue = "j"
                else:
                    queue = " "
                prefix = queue + alert + " "
                info = printer['printer-location']
            status_list.append("{}{}\t{}".format(prefix, printer_name, info))
            listed_printers.append(printer_name)
        heading = " ".join(filename.split(".")).upper()
        if status_list:
            print heading
            print "\n".join(status_list)
            print
        elif not (args.alerts or args.printer):
            # Only print empty sections in the summary view.
            print heading
            print "   (no printers)"
            print
    if args.test:
        confirmations = ['y', 'yes']
        confirm = raw_input("Print to {} listed printers? ".format(len(listed_printers)))
        if confirm in confirmations:
            print "Confirmed."
            for printer in listed_printers:
                test_printer(printer)
        else:
            print "Aborted."

if args.jobs:
    for job_id in job_list:
        display_job(job_id)

