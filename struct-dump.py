import sys
import json
import re
import pickle
import argparse
import os
import math

entries = {}

def memberOffset(input):
    match = re.match( r' .*\(DW_OP_plus_uconst: (\w+)\)', input)

    if not match:
        print('Unable to extract member offset from: "' + input + '"')
        return False

    return int(match.group(1))

def extractName(input):
    if ':' in input:
        match = re.match( r'.*: (.*)\w*', input)

        if not match:
            print('Unable to extract type name for: "' + input + '"')
            return False

        return match.group(1).strip()
    else:
        return input.strip()

def extractTypeNumber(input):
    input = input.strip()
    input = input[1:-1]
    return int(input, 16)


def parseTypedef(file, offset, properties):
    name = ''

    if 'DW_AT_name' in properties:
        name = extractName(properties['DW_AT_name'])

        if not name:
            print("Failed to extract name")
            return False
    else:
        return True

    typedef = {}
    typedef['name'] = name
    typedef['type'] = 'typedef'
    typedef['baseType'] = extractTypeNumber(properties['DW_AT_type'])
    entries[offset] = typedef

def parseStruct(file, offset, properties):
    name = ''

    if 'DW_AT_name' in properties:
        name = extractName(properties['DW_AT_name'])

        if not name:
            print("Failed to extract name")
            return False
    else:
        return True

    struct = {}
    struct['name'] = name
    struct['type'] = 'struct'

    entry = parseEntry(file)
    filePos = file.tell()
    members = {}

    while entry['level'] == 2:
        member = {}

        if 'DW_AT_name' in entry['properties'] and 'DW_AT_type' in entry['properties']:
            name = extractName(entry['properties']['DW_AT_name'])

            if not name:
                return False

            member['type'] = extractTypeNumber(entry['properties']['DW_AT_type'])
            member['offset'] = memberOffset(entry['properties']['DW_AT_data_member_location'])
            members[name] = member

        filePos = file.tell()
        entry = parseEntry(file)

    file.seek(filePos)

    struct['members'] = members
    entries[offset] = struct
    return True

def parseType(offset, properties):
    if 'DW_AT_name' not in properties:
        print("No DW_AT_name in entry")
        return False

    typeName = extractName(properties['DW_AT_name'])

    typeEntry = {}
    typeEntry['name'] = typeName
    typeEntry['type'] = 'base'
    entries[offset] = typeEntry

def parseEntry(file):
    line = file.readline()

    match = re.match( r' <(\w+)><(\w+)>: Abbrev Number: \w+ \((\w+)\)', line)

    if not match:
        return False

    level = int(match.group(1))
    offset = int(match.group(2), 16)
    type = match.group(3)

    filePosition = file.tell()
    counter = 0
    line = file.readline()

    properties = {}

    while line:
        if not line.startswith('    '):
            file.seek(filePosition)
            return {'offset': offset,
                    'level': level,
                    'type': type,
                    'properties': properties}

        match = re.match( r'    <\w+>   (\w+)\s*:(.*)', line)

        if not match:
            print("Failed to match: " + line)
            return False

        properties[match.group(1)] = match.group(2)

        filePosition = file.tell()
        line = file.readline()

def parseLevelOne(file):

    filePos = file.tell()
    entry = parseEntry(file)

    while entry and entry['level'] != 0:
        if not entry:
            print("Failed to parse entry")
            return False

        if entry['type'] == 'DW_TAG_base_type':
            parseType(entry['offset'], entry['properties'])
        elif entry['type'] == 'DW_TAG_structure_type':
            parseStruct(file, entry['offset'], entry['properties'])
        elif entry['type'] == 'DW_TAG_typedef':
            parseTypedef(file, entry['offset'], entry['properties'])

        filePos = file.tell()
        entry = parseEntry(file)

    file.seek(filePos)
    return True

def lookupType(input):
    if input not in entries:
        return (False, '')

    entry = entries[input]

    if entry['type'] == 'typedef':
        return lookupType(entry['baseType'])
    elif entry['type'] == 'base':
        return (entry['name'], 'baseType')
    elif entry['type'] == 'struct':
        return (entry['name'], 'struct')

    return (False, '')

def generateStructJson(offset):
    jsonStruct = {}

    struct = entries[offset]
    dependentTypes = []

    for memberName in struct['members']:
        (name, variant) = lookupType(struct['members'][memberName]['type'])

        if name:
            jsonStruct[memberName] = {'type': name, 'offset': struct['members'][memberName]['offset']}

            if variant == 'struct':
                dependentTypes.append(name)

    return (jsonStruct, dependentTypes)

def structJson(structName):
    for offset in entries:
        if entries[offset]['type'] == 'struct':
            struct = entries[offset]

            if struct['name'] ==  structName:
                (struct, dependentTypes) = generateStructJson(offset)
                jsonDOM[struct['name']] = struct

                writtenStructs.append(struct['name'])


def generateJson(structNames):
    jsonDOM = {}
    writtenStructs = []

    while structNames:
        structName = structNames.pop()

        for offset in entries:
            if entries[offset]['type'] == 'struct':
                entry = entries[offset]

                if entry['name'] == structName:
                    (struct, dependentStructs) = generateStructJson(offset)

                    if len(struct) > 0:
                        if structName in jsonDOM and jsonDOM[structName] != struct:
                            print(structName + " already defined, but with content.", file=sys.stderr)
                            print("Previously read: " + structName + ": " + str(jsonDOM[structName]), file=sys.stderr)
                            print("New: " + structName + ": " + str(struct), file=sys.stderr)
                        else:
                            jsonDOM[structName] = struct

                    if structName not in writtenStructs:
                        writtenStructs.append(structName)

                    for dependentStruct in dependentStructs:
                        if dependentStruct not in writtenStructs and dependentStruct not in structNames:
                            structNames.append(dependentStruct)
    return jsonDOM

def parseCompilationUnit(file):
    line = file.readline()

    if not line.startswith('  Compilation Unit @ offset '):
        return False

    for i in range(0, 4):
        line = file.readline()

    # Read the entry of CU
    entry = parseEntry(file)

    # Read everything else which is on level 1
    if not parseLevelOne(file):
        return False

    return True

parser = argparse.ArgumentParser()
parser.add_argument('-s', help='Structs to include', required=True)
parser.add_argument('-o', help='Output file', required=True)
parser.add_argument('objdump')

args = parser.parse_args()
file = open(args.s, 'r')
structs = json.loads(file.read())
file.close()

cached = False

if os.path.isfile(args.objdump) == False:
    print('Cannot open file: ' + args.objdump)
    exit(1)

if os.path.isfile('cache.bin'):
    if os.path.getmtime('cache.bin') > os.path.getmtime(args.objdump):
        cached = True

if not cached:
    print('Parsing objdump output from: "' + args.objdump + '"...')

    file = open(args.objdump, 'r')

    for i in range(0, 5):
        line = file.readline()

    result = parseCompilationUnit(file)

    while result:
        result = parseCompilationUnit(file)

    print('Parsed ' + str(len(entries)) + ' entries')

    cacheFile = open(r'cache.bin', 'wb')
    pickle.dump(entries, cacheFile)
    cacheFile.close()

    file.close()

else:
    cacheFile = open(r'cache.bin', 'rb')
    entries = pickle.load(cacheFile)
    print('Loaded ' + str(len(entries)) + ' entries from cache')
    cacheFile.close()

jsonStructure = generateJson(structs)
jsonText = json.dumps(jsonStructure, sort_keys=True, indent=4, separators=(',', ': '))

file = open(args.o, 'w')
file.write(jsonText)

size = len(jsonText)
sizeString = ""

if size < 1024:
    sizeString = str(size) + " bytes"
else:
    sizeString = "approximately " + str(math.floor(size / 1024)) + " KiB"

print("Wrote " + sizeString + " of struct data to \"" + args.o +"\"")

file.close()







