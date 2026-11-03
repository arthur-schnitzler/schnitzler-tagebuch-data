#!/usr/bin/env python3
"""
Collect the PMB entities used in a project's TEI index files (list*.xml) and
write them to a CSV that PMB reads to keep its URI registrations up to date.
PMB compares the CSV with the URIs it stores for the domain, see
`python manage.py sync_uris_in_use` in pmb-service. The project only delivers
the current state, the diff is done by PMB.

The script is project-independent; everything project-specific lives in a JSON
config (default: ./pmb-uris.json):

    domain         identifies the project in PMB (scopes additions/deletions)
    uri_template   URI of an entity page, {xml_id} and {pmb_id} are available
    index_glob     glob for the index files
    exclude        file names to skip (optional)
    id_pattern     regex applied to @xml:id; group 1 is the numeric PMB id
    output         path of the CSV

Output columns: pmb_id, entity_type, uri, domain
Rows are sorted by (entity_type, pmb_id) so that git diffs stay small.

The lists may sit anywhere in the body (body/listPerson, body/div/listPerson,
body/p/listBibl, ...). The entity type is taken from the entry itself (person,
place, org, bibl, event), not from the list around it. Entries of any other kind
(e.g. personGrp) are skipped, and so is a second entry for the same entity, also
if its xml:id only differs in leading zeros (pmb7, pmb007): PMB expects one row
per (entity_type, pmb_id). Everything skipped is reported.

Usage: process_list_xml.py [config.json]
"""

import csv
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

TEI = '{http://www.tei-c.org/ns/1.0}'
XML_ID = '{http://www.w3.org/XML/1998/namespace}id'

# TEI elements of the entries -> PMB entity types
ENTITY_TYPES = ['person', 'place', 'org', 'bibl', 'event']


def entries(element, in_list=False):
    """Yield the children of every list* element below element, however deeply
    the lists are wrapped in div or p. Entries are not searched themselves, they
    may contain lists of their own (listEvent, listBibl, ...)."""
    for child in element:
        is_list = child.tag.startswith(f'{TEI}list')
        if in_list and not is_list:
            yield child
        else:
            yield from entries(child, is_list)


def collect(config):
    id_re = re.compile(config['id_pattern'])
    excluded = set(config.get('exclude', []))
    files = sorted(
        f for f in glob.glob(config['index_glob'])
        if os.path.basename(f) not in excluded
    )

    rows = {}
    for path in files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as e:
            sys.exit(f'Error parsing {path}: {e}')
        body = root.find(f'.//{TEI}text/{TEI}body')
        if body is None:
            continue
        for entry in entries(body):
            xml_id = entry.get(XML_ID)
            if not xml_id:
                continue
            entity_type = entry.tag.removeprefix(TEI)
            if entity_type not in ENTITY_TYPES:
                print(f'Skipping {xml_id} in {path}: <{entity_type}> is not a PMB entity type')
                continue
            m = id_re.match(xml_id)
            if not m:
                print(f'Skipping {xml_id} in {path}: does not match id_pattern')
                continue
            pmb_id = int(m.group(1))
            if (entity_type, pmb_id) in rows:
                print(f'Skipping {xml_id} in {path}: duplicate {entity_type} {pmb_id}')
                continue
            uri = config['uri_template'].format(xml_id=xml_id, pmb_id=pmb_id)
            rows[(entity_type, pmb_id)] = [
                pmb_id, entity_type, uri, config['domain']]
    return files, [rows[k] for k in sorted(rows)]


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else 'pmb-uris.json'
    with open(config_path, encoding='utf-8') as f:
        config = json.load(f)

    files, rows = collect(config)
    if not rows:
        # An empty CSV would make PMB drop every registration of this domain.
        sys.exit('No entities found, refusing to write an empty CSV')

    output = config['output']
    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    with open(output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['pmb_id', 'entity_type', 'uri', 'domain'])
        writer.writerows(rows)

    print(f'Processed {len(files)} XML files')
    print(f'Extracted {len(rows)} entries')
    print(f'Output written to {output}')


if __name__ == '__main__':
    main()
