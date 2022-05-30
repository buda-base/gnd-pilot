import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, OWL, Namespace, NamespaceManager, XSD
import csv
import pathlib
import re
from transliterate import translit

PREFIXMAP = {
    "http://purl.bdrc.io/resource/": "bdr",
    "http://id.loc.gov/ontologies/bibframe/": "bf",
    "http://purl.bdrc.io/ontology/core/": "bdo",
    "http://purl.bdrc.io/admindata/": "bda",
    "http://purl.bdrc.io/ontology/admin/": "adm",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs",
    "http://www.w3.org/2004/02/skos/core#": "skos",
    "http://purl.dila.edu.tw/resource/": "dila",
    "http://purl.bdrc.io/ontology/tmp/": "tmp"
}

BDR = Namespace("http://purl.bdrc.io/resource/")
TMP = Namespace("http://purl.bdrc.io/ontology/tmp/")
BF = Namespace("http://id.loc.gov/ontologies/bibframe/")
BDO = Namespace("http://purl.bdrc.io/ontology/core/")
BDA = Namespace("http://purl.bdrc.io/admindata/")
ADM = Namespace("http://purl.bdrc.io/ontology/admin/")
DILA = Namespace("http://purl.dila.edu.tw/resource/")

EDTF = URIRef("http://id.loc.gov/datatypes/edtf")

NSM = NamespaceManager(rdflib.Graph())
NSM.bind("bdr", BDR)
NSM.bind("bdo", BDO)
NSM.bind("bf", BF)
NSM.bind("bda", BDA)
NSM.bind("adm", ADM)
NSM.bind("skos", SKOS)
NSM.bind("owl", OWL)
NSM.bind("rdfs", RDFS)
NSM.bind("dila", DILA)
NSM.bind("tmp", TMP)

rdflib.term._toPythonMapping.pop(rdflib.XSD['gYear'])

def get_winfos():
    winfos = {}
    iginfos = {}
    with open('input/Catalog template - ImageGroup _ Scroll.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            w = row[2][1:]
            if w not in winfos:
                winfos[w] = {'id': w, 'ig': []}
            iginfo = {'id': row[0], 'nbimages': 0, 'w': w}
            iginfos[row[0]] = iginfo
            winfos[w]['ig'].append(iginfo)
    with open('input/Catalog template - Images.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[1] not in iginfos:
                print("error: "+row[1]+" referenced in images but not in image scrolls")
                continue
            winfo = winfos[iginfos[row[1]]['w']]
            if 'th' not in winfo:
                winfo['th'] = "https://iiif.bdrc.io/bdr:"+row[1]+"::"+row[0]
            iginfos[row[1]]['nbimages'] += 1
    return winfos

def add_work(row, g, with_inferred):
    # 0 : bdrc id
    # 1: Prakras id
    # 2: title
    # 3: parallels in
    # 4: summary
    # 5: language
    # 6: topics
    # 7: Prakras URL
    main = BDR[row[0]]
    g.add((main, RDF.type, BDO.Work))
    admin = BDA[row[0]]
    g.add((admin, RDF.type, BDA.AdminData))
    g.add((admin, ADM.adminAbout, main))
    g.add((admin, ADM.status, BDA.StatusReleased))
    g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((main, SKOS.prefLabel, Literal(row[2], lang="en")))
    g.add((main, RDFS.seeAlso, URIRef(row[7])))

def add_topic(row, g, with_inferred):
    pass

def add_instance(row, g, with_inferred):
    # 0: id
    # 1: Prakraś ID
    # 2: version of
    # 3: Part of
    # 4: part type
    # 5: image range
    # 6: collection
    # 7: title
    # 8: description
    # 9: script
    # 10: material
    # 11: binding
    # 12: Prakraś URL
    # 13: condition
    # 14: width
    # 15: height
    # 16: gandari.org item
    # 17: date
    # bdr:PrintMethod_Manuscript always true
    main = BDR[row[0]]
    g.add((main, RDF.type, BDO.Instance))
    if row[3] == "":
        admin = BDA[row[0]]
        g.add((admin, RDF.type, BDA.AdminData))
        g.add((admin, ADM.adminAbout, main))
        g.add((admin, ADM.status, BDA.StatusReleased))
        g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
        g.add((main, BDO.instanceHasReproduction, BDR[row[0][1:]]))
    else:
        g.add((main, BDO.partOf, BDR[row[3]]))
        if with_inferred:
            g.add((BDR[row[3]], BDO.hasPart, main))
        if row[4] != "":
            g.add((main, BDO.partType, BDR[row[4]]))
        if row[5] != "":
            [spage, epage] = row[5].split('-')
            cl = BDR["CL"+row[0]+"_001"]
            g.add((main, BDO.contentLocation, cl))
            g.add((cl, RDF.type, BDO.ContentLocation))
            g.add((cl, BDO.contentLocationEndPage, Literal(epage, datatype=XSD.integer)))
            g.add((cl, BDO.contentLocationPage, Literal(spage, datatype=XSD.integer)))
            g.add((cl, BDO.contentLocationVolume, Literal(1, datatype=XSD.integer)))
            g.add((cl, BDO.contentLocationInstance, BDR[row[3][1:]]))
    g.add((main, BDO.printMethod, BDR.PrintMethod_Manuscript))
    if row[2] != "":
        g.add((main, BDO.instanceOf, BDR[row[2]]))
        if with_inferred:
            g.add((BDR[row[2]], BDO.workHasInstance, main))
    if row[6] != "":
        g.add((main, BDO.inCollection, BDR[row[6]]))
        if with_inferred:
            g.add((BDR[row[6]], BDO.collectionMember, main))
    titlelang = "sa-x-ewts"
    title = row[7]
    if title.endswith("@en"):
        title = title[:-3].strip()
        titlelang = "en"
    titleL = Literal(title, lang=titlelang)
    g.add((main, SKOS.prefLabel, titleL))
    titleR = BDR["TT"+row[0]+"_001"]
    g.add((main, BDO.hasTitle, titleR))
    g.add((titleR, RDFS.label, titleL))
    g.add((titleR, RDF.type, BDO.Title))
    if row[9] != "":
        g.add((main, BDO.script, BDR[row[8]]))
    if row[10] != "":
        g.add((main, BDO.material, BDR[row[10]]))
    if row[11] != "":
        g.add((main, BDO.binding, BDR[row[11]]))
    if row[17] != "":
        ev = BDR["EV"+row[0]+"_CE"]
        g.add((main, BDO.instanceEvent, ev))
        g.add((ev, BDO.eventWhen, Literal(row[17], datatype=EDTF)))
        g.add((ev, RDF.type, BDR.CopyEvent))

def add_iinstance(winfo, g, with_inferred):
    main = BDR[winfo['id']]
    admin = BDA[winfo['id']]
    g.add((admin, RDF.type, BDA.AdminData))
    g.add((admin, ADM.adminAbout, main))
    g.add((admin, ADM.status, BDA.StatusReleased))
    g.add((admin, ADM.access, BDA.AccessOpen))
    g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((admin, ADM.contentLegal, BDA.LD_BDRC_PD))
    g.add((admin, ADM.restrictedInChina, Literal(False)))
    g.add((main, RDF.type, BDO.ImageInstance))
    g.add((main, TMP.thumbnailIIIFService, URIRef(winfo['th'])))
    g.add((BDR["M"+winfo['id']], TMP.thumbnailIIIFService, URIRef(winfo['th'])))
    if with_inferred:
        g.add((main, BDO.instanceReproductionOf, BDR["M"+winfo['id']]))
    vnum = 1
    for iginfo in winfo['ig']:
        igmain = BDR[iginfo['id']]
        igadmin = BDA[iginfo['id']]
        g.add((igadmin, RDF.type, BDA.AdminData))
        g.add((igadmin, ADM.adminAbout, igmain))
        g.add((igadmin, ADM.status, BDA.StatusReleased))
        g.add((igadmin, ADM.access, BDA.AccessOpen))
        g.add((igadmin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
        g.add((igmain, RDF.type, BDO.ImageGroup))
        g.add((igmain, BDO.volumeNumber, Literal(vnum, datatype=XSD.integer)))
        vnum += 1
        g.add((igmain, BDO.volumePagesTbrcIntro, Literal(0, datatype=XSD.integer)))
        g.add((igmain, BDO.volumePagesTotal, Literal(iginfo['nbimages'], datatype=XSD.integer)))
        g.add((main, BDO.instanceHasVolume, igmain))
        if with_inferred:
            g.add((igmain, BDO.volumeOf, main))

def add_collection(row, g, with_inferred):
    # 0: bdrc id
    # 1: URL
    # 2: label
    # 3: description
    main = BDR[row[0]]
    g.add((main, RDF.type, BDO.Collection))
    admin = BDA[row[0]]
    g.add((admin, RDF.type, BDA.AdminData))
    g.add((admin, ADM.adminAbout, main))
    g.add((admin, ADM.status, BDA.StatusReleased))
    g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((main, SKOS.prefLabel, Literal(row[2], lang="en")))
    g.add((main, RDFS.seeAlso, URIRef(row[1])))

def main():
    g = rdflib.Graph()
    g.bind("bdr", BDR)
    g.bind("bdo", BDO)
    g.bind("bda", BDA)
    g.bind("adm", ADM)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    with open('input/Catalog template - Works _ Texts.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            add_work(row, g, True)
    with open('input/Catalog template - Version _ Manuscript.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            add_instance(row, g, True)
    with open('input/Catalog template - Collection.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            add_collection(row, g, True)
    winfos = get_winfos()
    for w, winfo in winfos.items():
        add_iinstance(winfo, g, True)
    g.serialize("GND.ttl", format="turtle")

main()