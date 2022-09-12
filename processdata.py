import rdflib
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, RDFS, SKOS, OWL, Namespace, NamespaceManager, XSD
import csv
import pathlib
import re
from transliterate import translit
import json
from copy import deepcopy
import hashlib

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

BVM_HOME = "../buda-volume-manifests/"

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
            iginfo = {'id': row[0], 'nbimages': 0, 'w': w, 'label_en': row[3]}
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

def add_einstance(row, g, with_inferred, winfos):
    # 0: id
    # 1: part of
    # 2: reproduction of
    # 3: Title
    # 4: text content
    main = BDR[row[0]]
    basename = row[0]
    volnum = 1
    if row[1] == "":
        g.add((main, RDF.type, BDO.EtextInstance))
        g.add((main, BDO.instanceReproductionOf, BDR[row[2]]))
        g.add((main, BDO.contentMethod, BDR.ContentMethod_ComputerInput))
        if with_inferred:
            g.add((main, RDF.type, BDO.Instance))
            g.add((main, RDF.type, BDO.DigitalInstance))
            g.add((BDR[row[2]], BDO.instanceHasReproduction, main))
        admin = BDA[row[0]]
        g.add((admin, RDF.type, BDA.AdminData))
        g.add((admin, ADM.adminAbout, main))
        g.add((admin, ADM.status, BDA.StatusReleased))
        g.add((admin, ADM.access, BDA.AccessOpen))
        g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    else:
        main = BDR[row[1]]
        basename = row[1]
        volnum = int(row[0][-3:])
    if row[4] != "":
        vol = BDR["VL"+basename]
        g.add((main, BDO.instanceHasVolume, vol))
        g.add((vol, RDF.type, BDO.VolumeEtextAsset))
        g.add((vol, BDO.volumeNumber, Literal(1, datatype=XSD.integer)))
        if with_inferred:
            g.add((vol, BDO.volumeOf, main))
        er = BDR["ERVL"+row[0]]
        g.add((vol, BDO.volumeHasEtext, er))
        g.add((er, RDF.type, BDO.EtextRef))
        g.add((er, BDO.seqNum, Literal(volnum, datatype=XSD.integer)))
        ut = BDR["UT"+row[0]]
        g.add((er, BDO.eTextResource, ut))
        g.add((ut, BDO.eTextInInstance, main))
        g.add((ut, SKOS.prefLabel, Literal(row[3], lang="sa-x-iast")))
        g.add((ut, RDF.type, BDO.EtextNonPaginated))
        c = BDR["ECUT"+row[0]]
        g.add((ut, BDO.eTextHasChunk, c))
        g.add((c, RDF.type, BDO.EtextChunk))
        g.add((c, BDO.chunkContents, Literal(row[4], lang="sa-x-iast")))
        g.add((c, BDO.sliceStartChar, Literal(0, datatype=XSD.integer)))
        g.add((c, BDO.sliceEndChar, Literal(len(row[4]), datatype=XSD.integer)))
        p = BDR["EPUT"+row[0]]
        g.add((p, RDF.type, BDO.EtextPage))
        g.add((p, BDO.sliceStartChar, Literal(0, datatype=XSD.integer)))
        g.add((p, BDO.sliceEndChar, Literal(len(row[4]), datatype=XSD.integer)))
        g.add((p, BDO.seqNum, Literal(1, datatype=XSD.integer)))

def add_instance(row, g, with_inferred, winfos):
    # 0: id
    # 1: Prakraś ID
    # 2: collection
    # 3: title
    # 4: description
    # 5: script
    # 6: material
    # 7: binding
    # 8: external URL
    # 9: condition
    # 10: width
    # 11: height
    # 12: gandari.org item
    # 13: date
    # 14: scanInfo
    # 15: path
    # bdr:PrintMethod_Manuscript always true
    main = BDR[row[0]]
    g.add((main, RDF.type, BDO.Instance))
    winfo = winfos[row[0][1:]]
    #g.add((main, BDO.numberOfVolumes, Literal(len(winfo['ig']), datatype=XSD.integer)))
    admin = BDA[row[0]]
    g.add((admin, RDF.type, BDA.AdminData))
    g.add((admin, ADM.adminAbout, main))
    g.add((admin, ADM.status, BDA.StatusReleased))
    g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((main, BDO.instanceHasReproduction, BDR[row[0][1:]]))
    g.add((main, BDO.printMethod, BDR.PrintMethod_Manuscript))
    if row[2] != "":
        g.add((main, BDO.inCollection, BDR[row[2]]))
        if with_inferred:
            g.add((BDR[row[2]], BDO.collectionMember, main))
    titles = get_literals(row[3])
    i = 1
    for t in titles:
        g.add((main, SKOS.prefLabel, t))
        titleR = BDR["TT"+row[0]+"_00"+str(i)]
        g.add((main, BDO.hasTitle, titleR))
        g.add((titleR, RDFS.label, t))
        g.add((titleR, RDF.type, BDO.Title))
        i += 1
    if row[4] != "":
        g.add((main, SKOS.description, Literal(row[4], lang="en")))
    if row[5] != "":
        g.add((main, BDO.script, BDR[row[5]]))
    if row[6] != "":
        g.add((main, BDO.material, BDR[row[6]]))
    if row[7] != "":
        g.add((main, BDO.binding, BDR[row[7]]))
    if row[8] != "":
        g.add((main, RDFS.seeAlso, BDR[row[8]]))
    if row[13] != "":
        ev = BDR["EV"+row[0]+"_CE"]
        g.add((main, BDO.instanceEvent, ev))
        g.add((ev, BDO.eventWhen, Literal(row[13], datatype=EDTF)))
        g.add((ev, RDF.type, BDO.CopyEvent))

def get_literals(col, default_lang="en"):
    res = []
    for l in col.split(","):
        l = l.strip()
        lang = "en"
        if "@" in l:
            l = l[:l.rfind('@')].strip()
            lang = "en"
        res.append(Literal(l, lang=lang))
    return res

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
        g.add((igmain, SKOS.prefLabel, Literal(iginfo['label_en'], lang="en")))
        g.add((igmain, BDO.volumePagesTotal, Literal(iginfo['nbimages'], datatype=XSD.integer)))
        g.add((main, BDO.instanceHasVolume, igmain))
        if with_inferred:
            g.add((igmain, BDO.volumeOf, main))
    g.add((main, BDO.numberOfVolumes, Literal(vnum, datatype=XSD.integer)))

def add_collection(row, g, with_inferred):
    # 0: bdrc id
    # 1: URL
    # 2: label
    # 3: description
    # 4: part of
    main = BDR[row[0]]
    g.add((main, RDF.type, BDO.Collection))
    admin = BDA[row[0]]
    g.add((admin, RDF.type, BDA.AdminData))
    g.add((admin, ADM.adminAbout, main))
    g.add((admin, ADM.status, BDA.StatusReleased))
    g.add((admin, ADM.metadataLegal, BDA.LD_BDRC_CC0))
    g.add((main, SKOS.prefLabel, Literal(row[2], lang="en")))
    if row[3]:
        g.add((main, SKOS.description, Literal(row[3], lang="en")))
    if row[4]:
        g.add((main, BDO.subCollectionOf, BDR[row[4]]))
        g.add((BDR[row[4]], BDO.hasSubCollection, main))

def get_iginfos():
    iginfos = {}
    with open('input/Catalog template - ImageGroup _ Scroll.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[0] not in iginfos:
                iginfos[row[0]] = {}
            iginfos[row[0]]['w'] = row[2][1:]
    with open('input/Catalog template - Images.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[1] not in iginfos:
                print("error: "+row[1]+" referenced in images but not in image scrolls")
                continue
            if "il" not in iginfos[row[1]]:
                iginfos[row[1]]['il'] = []
            imginfo = {'s3fn': row[0], 'fsfn': row[2], 'stdfn': row[3]}
            iginfos[row[1]]['il'].append(imginfo)
    return iginfos

def produce_manifests():
    iginfos = get_iginfos()
    with open('bvm-template.json') as f:
        template = json.load(f)
        for ig, iginfo in iginfos.items():
            bvm = deepcopy(template)
            bvm["imggroup"] = "bdr:"+ig
            ilist = bvm["view"]["view1"]["imagelist"]
            for iinfo in iginfo["il"]:
                bvmiinfo = {}
                bvmiinfo["filename"] = iinfo["s3fn"]
                bvmiinfo["sourcePath"] = iinfo["fsfn"]
                ilist.append(bvmiinfo)
            md5 = hashlib.md5(str.encode(ig))
            two = md5.hexdigest()[:2]
            fpath = BVM_HOME+two+"/"+ig+".json"
            with open(fpath, 'w') as outfile:
                json.dump(bvm, outfile, indent=4, sort_keys=True, ensure_ascii=False)

def produce_ttl():
    g = rdflib.Graph()
    g.bind("bdr", BDR)
    g.bind("bdo", BDO)
    g.bind("bda", BDA)
    g.bind("adm", ADM)
    g.bind("skos", SKOS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    #with open('input/Catalog template - Works _ Texts.csv', newline='') as csvfile:
    #    reader = csv.reader(csvfile)
    #    next(reader)
    #    for row in reader:
    #        add_work(row, g, True)
    winfos = get_winfos()
    with open('input/Catalog template - Physical _ Item.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            add_instance(row, g, True, winfos)
    #with open('input/Catalog template - Digital Edition.csv', newline='') as csvfile:
    #    reader = csv.reader(csvfile)
    #    next(reader)
    #    for row in reader:
    #        add_einstance(row, g, True, winfos)
    with open('input/Catalog template - Collection.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            add_collection(row, g, True)
    for w, winfo in winfos.items():
        add_iinstance(winfo, g, True)
    g.serialize("GND.ttl", format="turtle")

def main():
    produce_ttl()
    produce_manifests()

main()