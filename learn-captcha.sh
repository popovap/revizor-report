#!/bin/bash

# Here we are pretending to be a Chrome and fetching a picture with a
# simple captcha. We show it to the user and wait for a response from
# the user with a number in the console and feed results to gocr that
# build its database for this particular captcha type. It took me
# about one hour to make gocr learn this captcha.

# Running of this tool suppose Linux desktop environment is used

rm cap-0.png cap-2.pbm index.html cookies.txt

while [ 1 ]; do
    # get page and captcha's url
    wget --no-check-certificate --header="Host: portal.rfc-revizor.ru" --header="User-Agent: Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36" --header="Accept-Language: ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4" --save-cookies cookies.txt --keep-session-cookies --header="Connection: keep-alive" "https://portal.rfc-revizor.ru/login/" -O index.html >/dev/null 2>&1
    cap_id=`grep captcha index.html | perl -e 'while (<>) {/\"\/captcha\/(\d+)\"/; print $1}'`
    cap_url="https://portal.rfc-revizor.ru/captcha/"$cap_id
# get captcha image file
    wget --no-check-certificate --header="Host: portal.rfc-revizor.ru" --header="User-Agent: Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36" --header="Accept-Language: ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4" --keep-session-cookies --load-cookies cookies.txt --header="Connection: keep-alive" $cap_url -O "cap-0.png" -c >/dev/null 2>&1
    # clear image
    #display cap-0.png &
    convert cap-0.png -morphology thicken '1x3>:2,0,2' -write MPR:source -clip-mask MPR:source -morphology erode:8 square +clip-mask -morphology close rectangle:3x3 cap-2.pbm
    #convert cap-0.png -morphology thicken '1x3>:7,0,5' cap-1.png
    #convert cap-1.png -fill white -fuzz 10% +opaque "#000000" cap-2.png
    # learn patterns
    gocr -d 2 -p ./ocrdb/ -m 256 -m 130 cap-2.pbm ;
    rm cap-0.png cap-2.pbm index.html cookies.txt
done
