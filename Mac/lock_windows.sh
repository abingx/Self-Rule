#!/bin/bash
ssh xueOffice@192.168.31.130 "for /f \"skip=1 tokens=3\" %s in ('query user %USERNAME%') do tsdiscon %s"