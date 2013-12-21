#!/usr/bin/python

import cups, argparse, tempfile, os, sys, smtplib, pwd, ConfigParser
from glob import glob
from urllib2 import urlopen
from email.mime.text import MIMEText


# Command line options and help output.
parser = argparse.ArgumentParser(description="""
CAT Printer Information Generator. Get status of printers whose names match
all the substrings provided (if any are), either from lists given in
~/.catpig/*.printers or directly from cups; send test pages; manage jobs.
""")
parser.add_argument("printer", metavar="PRINTER", nargs="*",
    help="substrings of printer names to look for")
parser.add_argument("-a", "--alerts", action="store_true",
    help="show printers which have alerts, and list them")
parser.add_argument("-j", "--jobs", action="store_true",
    help="show printers which have unfinished jobs, and list them")
parser.add_argument("-v", "--verbose", action="store_true",
    help="show detailed information for the selected printers")
parser.add_argument("-t", "--test", action="store_true",
    help="prompt to send a test to selected printers")
parser.add_argument("-k", "--kill", action="store_true",
    help="prompt to kill any unfinished jobs which are listed")
parser.add_argument("-c", "--cups", action="store_true",
    help="use printer list from cups instead of ~/.catpig/*.printers")
args = parser.parse_args()


def print_error(message):
    """Prints a message to stderr followed by a newline."""
    sys.stderr.write("{}\n".format(message))


def pretty_string(message):
    """Cleans up e.g. printer status messages for user-facing display."""
    message = str(message)
    try:
        most, last = message.rsplit("-", 1)
        if last in ["warning", "report"]:
            message = most
    except ValueError:
        pass
    return message.replace("-", " ").title()


def print_job(conn, job):
    """Prints the ID, filename, user, and status of a print job."""
    status = pretty_string(job["job-state-reasons"][4:])
    if "job-printer-state-message" in job:
        message = job["job-printer-state-message"]
        status = " -- {} ({})".format(status, message)
    user = job["job-originating-user-name"]
    name = job["job-name"]
    job_id = job["job-id"]
    print "{}  {} ({}){}".format(job_id, name, user, status)
    if args.kill:
        kill_job(conn, job)


def print_details(printer, jobs):
    """Prints detailed information about a printer's location and status."""
    printer_name = printer["printer-uri-supported"].rsplit("/", 1)[1]
    print "Printer Name:\t{}".format(printer_name)
    print "Location:\t{}".format(printer["printer-location"])
    print "Model:\t\t{}".format(printer["printer-make-and-model"])

    if "printer-state-message" in printer and printer["printer-state-message"]:
        print "Status:\t\t{}".format(printer["printer-state-message"])
    if printer["printer-state-reasons"][0] != "none":
        first_message = printer["printer-state-reasons"].pop()
        print "Messages:\t{}".format(pretty_string(first_message))
        for reason in printer["printer-state-reasons"]:
            print "\t\t{}".format(pretty_string(reason))

    if jobs:
        print "Jobs:\t\t",
        print_job(conn, jobs[0])
        for job in jobs[1:]:
            print "\t\t",
            print_job(conn, job)
    print


def print_summary(conn, printer, jobs):
    """Prints a one-line summary about a printer."""
    printer_name = printer["printer-uri-supported"].rsplit("/", 1)[1]
    if printer["printer-state-reasons"][0] != "none":
        alert = "!"
    else:
        alert = " "
    if len(jobs):
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
        for job in jobs:
            print "   .",
            print_job(conn, job)


def kill_job(conn, job):
    """Kills a job, with confirmation; optionally, sends email to the user."""
    job_id = job["job-id"]
    printer_name = job["job-printer-uri"].rsplit("/", 1)[1]

    confirm = raw_input("Cancel job #{} on {}? ".format(job_id, printer_name))
    if confirm not in CONFIRMATIONS:
        print_error("Aborted.")
        return

    try:
        conn.cancelJob(job_id)
        print_error("Job removed.")
    except cups.IPPError as (status, description):
        print "Unable to remove job (\"{}\").".format(pretty_string(description))
        return

    confirm = raw_input("Send email? ")
    if confirm not in CONFIRMATIONS:
        print_error("Aborted.")
        return

    email_vars = {
        "user": job["job-originating-user-name"],
        "me": pwd.getpwuid(os.getuid()).pw_name,
        "name": job["job-name"],
        "printer": printer_name
    }

    try:
        config_file = os.path.join(BASEDIR, "config")
        with open(config_file) as fp:
            config = ConfigParser.ConfigParser()
            config.optionxform = str
            config.readfp(fp)
    except IOError:
        print_error("Couldn't read config file: {}".format(config_file))
        return

    try:
        body_file = os.path.join(BASEDIR, config.get("Job Email Body", "body"))
        with open(body_file) as fp:
            body = fp.read()
    except KeyError:
        print_error("No message body filename found. (It should be in "
                    "the option 'body' and section 'Job Email Body'.)")
        return
    except IOError:
        print_error("Couldn't read email body file: " "{}".format(body_file))
        return

    try:
        sig_file = os.path.join(BASEDIR,
                                config.get("Job Email Body", "signature"))
        with open(sig_file) as fp:
            signature = fp.read()
        body += "\n" + signature
    except KeyError:
        print_error("(No signature filename found, continuing anyway.)")
    except IOError:
        print_error("Couldn't read signature file: {}".format(sig_file))
        return

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
        return

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


def test_printer(conn, printer_name):
    """Sends a test page to the printer, with confirmation."""
    confirm = raw_input("Send test page to {}? ".format(printer_name))
    if confirm in CONFIRMATIONS:
        print_error("Fetching test page data ...")
        animal = urlopen("http://www.lorempixel.com/800/600/animals").read()
        with tempfile.NamedTemporaryFile() as fp:
            fp.write(animal)
            print_error("Fetched. Printing ...")
            conn.printFile(printer_name, fp.name, "CATPIG Test", {})
        print_error("Done.")
    else:
        print_error("Aborted.")


def main():
    # Connect to cups and get job and printer information.
    conn = cups.Connection()
    all_printers = conn.getPrinters()
    jobs = conn.getJobs()

    if args.cups:
        matched_printers = all_printers
    else:
        # Open *.printers files and build printer name lists.
        matched_printers = []
        printer_lists = glob(os.path.join(BASEDIR, "*.printers"))
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
            jobs_by_printer[printer].append(job)

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
        printer_exists = True
        try:
            printer = all_printers[printer_name]
        except KeyError:
            printer_exists = False

        if args.verbose:
            if printer_exists:
                print_details(printer, jobs_by_printer[printer_name])
            else:
                print "Printer Name:\t{}".format(printer_name)
                print "Location:\tNOT FOUND\n"
                return
        else:
            if printer_exists:
                print_summary(conn, printer, jobs_by_printer[printer_name])
            else:
                print "XX {}\tNOT FOUND".format(printer_name)
                return
        if args.test:
            test_printer(conn, printer_name)


CONFIRMATIONS = ["y", "yes"]
BASEDIR = os.path.join(os.path.expanduser("~"), ".catpig/")

if __name__ == "__main__":
    main()
