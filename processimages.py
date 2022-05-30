import sys
from collections import namedtuple
from urllib import request
import hashlib
import io
import json
import gzip
import os
import shutil
import csv

from PIL import Image

def getS3FolderPrefix(w, imageGroupID):
    """
    gives the s3 prefix (~folder) in which the volume will be present.
    inpire from https://github.com/buda-base/buda-iiif-presentation/blob/master/src/main/java/io/bdrc/iiif/presentation/ImageInfoListService.java#L73
    Example:
       - w=W22084, imageGroupID=I0886
       - result = "Works/60/W22084/images/W22084-0886/
    where:
       - 60 is the first two characters of the md5 of the string W22084
       - 0886 is:
          * the image group ID without the initial "I" if the image group ID is in the form I\d\d\d\d
          * or else the full image group ID (incuding the "I")
    """
    md5 = hashlib.md5(str.encode(w))
    two = md5.hexdigest()[:2]

    pre, rest = imageGroupID[0], imageGroupID[1:]
    if pre == 'I' and rest.isdigit() and len(rest) == 4:
        suffix = rest
    else:
        suffix = imageGroupID
    return 'Works/{two}/{RID}/images/{RID}-{suffix}/'.format(two=two, RID=w, suffix=suffix)

def ildatafromfsfn(fsfn):
    errors = []
    size = os.stat(fsfn).st_size
    im = Image.open(fsfn)
    data = {}
    data["width"] = im.width
    data["height"] = im.height
    # we indicate sizes of the more than 1MB
    if size > 1000000:
        data["size"] = size
    if size > 400000:
        errors.append("toolarge")
    compression = ""
    final4 = fsfn[-4:].lower()
    if im.format == "TIFF":
        compression = im.info["compression"]
        if im.info["compression"] != "group4":
            errors.append("tiffnotgroup4")
        if im.mode != "1":
            errors.append("nonbinarytif")
            data["pilmode"] = im.mode
        if final4 != ".tif" and final4 != "tiff":
            errors.append("extformatmismatch")
    elif im.format == "JPEG":
        if final4 != ".jpg" and final4 != "jpeg":
            errors.append("extformatmismatch")
    else:
        errors.append("invalidformat")
    # in case of an uncompressed raw, im.info.compression == "raw"
    print(errors)
    return data


def get_iginfos():
    iginfos = {}
    with open('input/Catalog template - ImageGroup _ Scroll.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[0] not in iginfos:
                iginfos[row[0]] = {}
            iginfos[row[0]]['w'] = row[2]
    with open('input/Catalog template - Images.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[1] not in iginfos:
                print("error: "+row[1]+" referenced in images but not in image scrolls")
                continue
            if "il" not in iginfos[row[1]]:
                iginfos[row[1]]['il'] = []
            imginfo = {'s3fn': row[0], 'fsfn': "images/"+row[2], 'stdfn': row[3]}
            iginfos[row[1]]['il'].append(imginfo)
    return iginfos

def gzip_str(s):
    # taken from https://gist.github.com/Garrett-R/dc6f08fc1eab63f94d2cbb89cb61c33d
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as fo:
        fo.write(s.encode())
    bytes_obj = out.getvalue()
    return bytes_obj

def main():
    iginfos = get_iginfos()
    print(iginfos)
    for ig, iginfo in iginfos.items():
        s3prefix = 's3/'+getS3FolderPrefix(iginfo['w'], ig)
        os.makedirs(s3prefix, exist_ok=True)
        manifest = []
        for imginfo in iginfo['il']:
            manifest.append(ildatafromfsfn(imginfo['fsfn']))
            shutil.copyfile(imginfo['fsfn'], s3prefix+imginfo['s3fn'])
        manifest_str = json.dumps(manifest)
        manifest_gzip = gzip_str(manifest_str)
        with open(s3prefix+"dimensions.json", "wb") as df:
            df.write(manifest_gzip)

if __name__ == '__main__':
    main()