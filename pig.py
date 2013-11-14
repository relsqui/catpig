#!/usr/bin/python

import cups, sys, argparse
from pprint import pprint


printer_lists = [
    'fab.printers',
    'eb.printers',
    'cat.printers',
]

confirmations = ['y', 'yes']


conn = cups.Connection()
all_printers = conn.getPrinters()

check_printers = []
printers_by_file = {}
for list_file in printer_lists:
    with open(list_file) as fp:
        printers_by_file[list_file] = [p.strip() for p in fp.readlines()]
        check_printers.extend(printers_by_file[list_file])

parser = argparse.ArgumentParser(description="Printer Information Generator. Get information on available printers and send test prints.")
parser.add_argument("printer", metavar="PRINTER", choices=check_printers, nargs="?", help="ID of printer (if absent, PIG will print a summary)")
parser.add_argument("-t", "--test", action='store_true', help="send a test page to the selected printer")
args = parser.parse_args()


if args.printer:
    try:
        printer = all_printers[args.printer]
    except KeyError:
        print "Sorry, can't reach {}. Run PIG with no arguments to get a printer list.".format(args.printer)
        sys.exit(1)
    print "Location:\t{}".format(printer['printer-location'])
    print "Model:\t\t{}".format(printer['printer-make-and-model'])
    if printer['printer-state-message']:
        print "Status:\t\t{}".format(printer['printer-state-message'])
    if printer['printer-state-reasons'][0] != "none":
        print "Messages:\t{}".format(printer['printer-state-reasons'].pop())
        for reason in printer['printer-state-reasons']:
            print "\t\t{}".format(reason)
    if args.test:
        print
        confirm = raw_input("Sending test page. Confirm? ")
        if confirm in confirmations:
            conn.printTestPage(args.printer)
            print "Confirmed, sending test page."
        else:
            print "Aborted."

else:
    for filename in printer_lists:
        print filename.upper()
        for printer_name in printers_by_file[filename]:
            if printer_name not in all_printers.keys():
                print "XX  {}\tNOT FOUND".format(printer_name)
                continue
            printer = all_printers[printer_name]
            if printer['printer-state-reasons'][0] != "none":
                print "!! ",
            else:
                print "   ",
            print "{}\t{}".format(printer_name, printer['printer-location'])
        print
