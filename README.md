# revizor-report

This shitty code was intended by me to automate going to the personal account of a user of the Russian system Revizor for telecom operators:

* creating there a request for a report on seep a URL through the URL-filtering system (big brother's DPI) for a certain period of time,
* waiting until the report is generated,
* loading the report and parsing it on the subject of errors and violations.
* in case of problems, the script should drop me a letter.

This script is run by cron with this job:
```00 06 * * * /usr/local/revizor-report/revizor-report.py```
