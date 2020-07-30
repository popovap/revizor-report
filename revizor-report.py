#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import logging.handlers
import subprocess
from sys import argv
import re
import os
from sys import exit
from datetime import date, timedelta
import time
import zipfile
import sys

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
filehandler = logging.handlers.TimedRotatingFileHandler('/var/log/revizor-report/revizor-report.log',when='midnight',interval=1,backupCount=10)
filehandler.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(filehandler)

logger.debug("Starting {}".format(argv[0]))

recipient = "admin@yandex.ru"
carboncopy="junioradmin@yandex.ru"
subject = "Revizor report INFO"
sender = "From: Revizor Report <admin@yandex.ru>"
operatorName = 'Твой интернет' # The name of the ISP gathered from personal area of portal.rfc-revizor.ru
username = 'admin@yandex.ru' 
password = 'kfc123' # Hey, Trump!
loginMaxRetries = 10
cookiesFile = 'cookies.txt'
capFile = 'cap-0.png'
capCleanFile = 'cap-clean.pbm'
gocrdb = './ocrdb/'
maxWaitTime = 600 # time to wait for report creation, seconds
reportsDir = 'reports'
installDir = '/usr/local/revizor-report' # directory where the root folder of all this shit is

os.chdir(installDir)

# test needed software
utils = ['/usr/bin/mail', '/usr/bin/wget', '/usr/bin/convert', '/usr/bin/gocr']
for util in utils:
    if not os.access(util, os.X_OK):
        msg = "Can\'t find runable %s" % util
        sys.exit(msg)

def sendemail(body, recipient=recipient, carboncopy=carboncopy, subject=subject, sender=sender):
    process = subprocess.Popen(['/usr/bin/mail', '-a', sender, '-s', subject, recipient, '-c', carboncopy],
                               stdin=subprocess.PIPE)
    logger.debug("sendemail: Sending email:\nTo: {}\nCC:{}\nBody:\n{}\n".format(recipient,carboncopy,body.decode()))
    process.communicate(body)

if os.access(cookiesFile, os.W_OK): os.remove(cookiesFile)
# page downloader
def mywget(url, options):
    wgetcmd = "/usr/bin/wget --no-check-certificate --header=\"Host: portal.rfc-revizor.ru\" --header=\"User-Agent: Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36\" --header=\"Accept-Language: ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4\" --header=\"Connection: keep-alive\" --keep-session-cookies %s -- %s" % (options, url)
    process = subprocess.Popen(wgetcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    logger.debug("mywget: STDERR: {}\n".format(error.decode()))
    return output

loginSuccess = 0
loginRetries = 0
while loginSuccess !=  1:
    loginRetries += 1
    if loginRetries > loginMaxRetries:
        break
    # clean previous run
    if os.access(capFile, os.W_OK): os.remove(capFile)
    if os.access(capCleanFile, os.W_OK): os.remove(capCleanFile)
    # getting capture image
    url = 'https://portal.rfc-revizor.ru/login/'
    myOptions = '--save-cookies %s -O -' % cookiesFile
    capId = re.findall(r'\"\/captcha\/(\d+)\"', mywget(url,myOptions).decode('utf-8'))[0]
    capURL = "https://portal.rfc-revizor.ru/captcha/%s" % capId
    myOptions = '--load-cookies %s -O %s' % (cookiesFile, capFile)
    mywget(capURL, myOptions)
    # clean image
    convertCmd = "/usr/bin/convert %s -morphology thicken '1x3>:2,0,2' -write MPR:source -clip-mask MPR:source -morphology erode:8 square +clip-mask -morphology close rectangle:3x3 %s" % (capFile, capCleanFile)
    convertProcess = subprocess.Popen(convertCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    convertOutput, convertError = convertProcess.communicate()
    logger.debug("convert: STDOUT:\n{}\nSTDERR:\n{}\n".format(convertOutput.decode(),convertError.decode()))
    # get digits
    gocrCmd = "/usr/bin/gocr -p %s -m 256 -m 2 %s" % (gocrdb, capCleanFile)
    gocrProcess = subprocess.Popen(gocrCmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    gocrOutput, gocrError = gocrProcess.communicate()
    logger.debug("convert: STDOUT:\n{}\nSTDERR:\n{}\n".format(gocrOutput.decode(),gocrError.decode()))
    digits = ''.join(re.findall(r'\d+', gocrOutput.decode()))
    logger.debug("Attempt {} digits: {}".format(loginRetries,digits))
    if (digits.count('')-1 < 3 or digits.count('')-1 > 4):
        next
    # try to login
    url = 'https://portal.rfc-revizor.ru/login/'
    myOptions = '--load-cookies %s --post-data=\"email=%s&password=%s&secretcodestatus=%s&secretcodeId=%s\" -O -' % (cookiesFile, username, password, digits, capId)
    afterLoginPage = mywget(url, myOptions)
    myRe = r'%s' % operatorName
    loginStatus = re.findall(myRe, afterLoginPage.decode() )
    loginSuccess = 1 if bool(loginStatus) else 0

if loginSuccess != 1:
    # email me
    body = "Проблемы с аутентификацией в личном кабинете оператора связи.\nКоличество попыток авторизоваться: %s\nПоследняя полученная страница: %s" % (loginRetries, afterLoginPage.decode())
    sendemail(body.encode())
    msg = "Не удалось войти в личный кабинет"
    sys.exit(msg)

# create report request for yesterday
reportDate = (date.today() - timedelta(1)).strftime('%d.%m.%Y')
# check if report is already created by someone
myRe = r'<td>%s</td>\s+<td></td>\s+<td>результат готов</td>' % reportDate
repListUrl = 'https://portal.rfc-revizor.ru/cabinet/claims-reports/'
myOptions = '--load-cookies %s -O -' % cookiesFile
reportListPage = mywget(repListUrl, myOptions)
alredyExists = re.findall(myRe, reportListPage.decode())
if not bool(alredyExists):
    createReportUrl = 'https://portal.rfc-revizor.ru/cabinet/myclaims-reports/create'
    myOptions = '--load-cookies %s --post-data=\"reportDate=%s\" -O -' % (cookiesFile, reportDate)
    afterRepReqPage = mywget(createReportUrl, myOptions)
    myRe = r'<td>(\d\d.\d\d.\d\d\d\d \d\d:\d\d)</td>\s+<td>%s</td>\s+<td></td>\s+<td>новый</td>' % reportDate
    createDate = re.findall(myRe, afterRepReqPage.decode())
    createDate = createDate[0]
    if bool(createDate):
        newExists = 1 
    else:
        body = "Проблемы с загрузкой отчетов из личного кабинета оператора связи.\n Попытка запроса на создание отёта завершилась неудачно.\nВремя создания запроса на отчёт: %s\nСтрока поиска: %s\nПоследняя полученная страница со списком отчётов: %s\n" % (reportDate, myRe, afterRepReqPage.decode())
        sendemail(body.encode())
        msg = "It seems we cant create request for report"
        sys.exit(msg)
else:
    # find report create date and time for reference
    myRe = r'<td>(\d\d.\d\d.\d\d\d\d \d\d:\d\d)</td>\s+<td>%s</td>\s+<td></td>\s+<td>результат готов</td>' % reportDate
    createDate = re.findall(myRe, reportListPage.decode())
    createDate = createDate[0]
    newExists = 0

# if report has not alredy created, wait for it creation
if bool(newExists):
    iterTime = 30
    elapsedTime = 0
    myRe = r'<td>%s</td>\s+<td>%s</td>\s+<td></td>\s+<td>новый</td>' % (createDate, reportDate)
    while bool(newExists):
        time.sleep(iterTime)
        elapsedTime += iterTime
        reportListPage = mywget(repListUrl, myOptions)
        # check if the report is not created
        newExists = re.findall(myRe, reportListPage.decode())
        if elapsedTime >= maxWaitTime:
            break
    if bool(newExists):
        # email me
        body = "Проблемы с загрузкой отчетов из личного кабинета оператора связи.\n Попытка получить отчет за %s\n Время создания запроса на отчёт: %s\nВремя ожидания подготовки отчёта: %s\nПоследняя полученная страница со списком отчётов: %s\n" % (reportDate, createDate, elapsedTime, reportListPage.decode())
        sendemail(body.encode())
        msg = "Не удалось дождаться формирования отчета"
        sys.exit(msg)

# get report
myRe = r'<td>%s</td>\s+<td>%s</td>\s+<td></td>\s+<td>результат готов</td>\s+<td>\d\d.\d\d.\d\d\d\d \d\d:\d\d </td>\s+<td><a href=\"/cabinet/claims-reports/download/(\d+).zip">скачать</a> </td>' % (createDate, reportDate)
reportID = re.findall(myRe, reportListPage.decode())
if reportID[0] == '':
    body = "Проблемы с загрузкой отчетов из личного кабинета оператора связи.\n Попытка получить отчет за %s\n Время создания запроса на отчёт: %s\nИдентификатор файла отчета: %s\nСтрока поиска: %s\nПоследняя полученная страница со списком отчётов: %s\n" % (reportDate, createDate, reportID, myRe, reportListPage.decode())
    sendemail(body.encode())
    msg = "Не удалось сформировать URL файла отчета"
    sys.exit(msg)
reportUrl = 'https://portal.rfc-revizor.ru/cabinet/claims-reports/download/%s.zip' % reportID[0]
reportFile = '%s/%s.zip' % (reportsDir, reportDate)
myOptions = '--load-cookies %s -O %s' % (cookiesFile, reportFile)
mywget(reportUrl, myOptions)
if not zipfile.is_zipfile(reportFile):
    body = "Проблемы с загрузкой отчетов из личного кабинета оператора связи.\nПолученный файл не является zip-архивом.\nПопытка получить отчет за %s\n Время создания запроса на отчёт: %s\nИдентификатор файла отчета: %s\nСтрока поиска: %s\nПоследняя полученная страница со списком отчётов: %s\nURL файла отчета: %s\nИмя скачанного файла отчёта: %s\n" % (reportDate, createDate, reportID, myRe, reportListPage.decode(), reportUrl, reportFile)
    sendemail(body.encode())
    msg = "Полученный файл не является ZIP архивом"
    sys.exit(msg)

# read report
with zipfile.ZipFile(reportFile, 'r') as zip_ref:
    zip_ref.extractall('./')
    zip_ref.close()
with open('report.csv', encoding='cp1251') as freport:
    reportText = freport.read()

noViolation = r'Мониторинг не выявил нарушений'
reportResult = re.findall(noViolation, reportText)
# notifying
if not bool(reportResult):
    # email me
    body = "В мониторинге нарушений URL-фильтрации имеются проблемы!\nОтчёт за %s:\n\n%s" % (reportDate, reportText)
    sendemail(body.encode())
else:
    #body = "Мониторинг пропущенных URL не выявил нарушений.\nОтчёт за %s:\n\n%s" % (reportDate, reportText)
    #sendemail(body.encode())
    # clean up
    if os.access('report.pdf', os.W_OK): os.remove('report.pdf')
    if os.access('report.csv', os.W_OK): os.remove('report.csv')
    if os.access(capFile, os.W_OK): os.remove(capFile)
    if os.access(capCleanFile, os.W_OK): os.remove(capCleanFile)
    if os.access(cookiesFile, os.W_OK): os.remove(cookiesFile)


