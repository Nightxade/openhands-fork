#!/bin/bash

vul="$id.submit-vul"
fix="$id.submit-fix"

xxd -c 10000000000 -p "$1" | nc vul 2001
xxd -c 10000000000 -p "$1" | nc fix 2002
