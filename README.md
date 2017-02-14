# struct-dump

struct-dump is a tool to extract C struct layout definitions from the debug info embedded in ELF files. It works in combination with GNU's objdump and is designed for embedded projects.

struct-dump works in combination with objdump in such way that objdump is first run to output the debug info to a file:

    objdump --dwarf firmware.elf > objdump.txt

Then struct-dump.py is called:

    struct-dump.py -s structs.json -o struct_dump.json objdump.txt

structs.json is a file containing a single JSON array denoting the structs of interest and may look like this:

    ["StructA", "StructB", "StructC"]



 
