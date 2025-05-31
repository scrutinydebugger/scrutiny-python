#    format_package_license.py
#        Internal script called by make_license.sh to print licenses of each given dependencies
#        in a given format
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2021 Scrutiny Debugger

import sys
import json
import piplicenses

packages = sys.argv[1:]

args = ['-p'] + packages
args += ['-f', 'json'] 
args += ['-d']   # description                                   
args += ['-u']   # url
args += ['-a']   # authors 
args += ['-l']   # License file

parser = piplicenses.create_parser()
parsed_args = parser.parse_args(args)
json_data = piplicenses.create_output_string(parsed_args)
data = json.loads(json_data)

tab="  "
for package in data:
    print("\n============================================\n")
    print(f"{package['Name']} {package['Version']}")
    print(f"{tab}{package['Description']}")
    if package['Author'] != 'UNKNOWN':
        print(f"{tab}- Author: {package['Author']}")
    if package['URL'] != 'UNKNOWN':
        print(f"{tab}- Source: {package['URL']}")
    print(f"{tab}- License: {package['License']}")
    print()
    if package['LicenseText'] != 'UNKNOWN':
        print(f"{tab}-License content:")
        lines = package['LicenseText'].splitlines()
        for line in lines:
            print(f"{tab}{tab}{line}")
