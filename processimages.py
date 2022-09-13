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

IMG_INPUT_PATH = "images/"
IMG_OUTPUT_PATH = "s3/"
OPTJPG_CMD = None # "/home/eroux/softs/mozjpeg/build/jpegtran-static"

if len(sys.argv) > 1:
    IMG_INPUT_PATH = sys.argv[1]

if len(sys.argv) > 2:
    IMG_OUTPUT_PATH = sys.argv[2]

if len(sys.argv) > 3:
    OPTJPG_CMD = sys.argv[3]    

def getS3FolderPrefix(w):
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

    return 'Works/{two}/{RID}/'.format(two=two, RID=w)

def getS3FolderIG(imageGroupID):
    pre, rest = imageGroupID[0], imageGroupID[1:]
    if pre == 'I' and rest.isdigit() and len(rest) == 4:
        suffix = rest
    else:
        suffix = imageGroupID
    return suffix

def ildatafromfsfn(fsfn, s3fn):
    errors = []
    size = os.stat(fsfn).st_size
    im = Image.open(fsfn)
    data = {}
    data["filename"] = s3fn
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

def get_source_folders():
    wfolderinfos = {}
    with open('input/Catalog template - Physical _ Item.csv', newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[15] == "":
                continue
            if row[0] in wfolderinfos:
                print("two folders for "+row[0])
                continue
            wfolderinfos[row[0][1:]] = row[15]
    return wfolderinfos

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
            imginfo = {'s3fn': row[0], 'fsfn': IMG_INPUT_PATH+row[2], 'stdfn': row[3]}
            iginfos[row[1]]['il'].append(imginfo)
    return iginfos

def gzip_str(s):
    # taken from https://gist.github.com/Garrett-R/dc6f08fc1eab63f94d2cbb89cb61c33d
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as fo:
        fo.write(s.encode())
    bytes_obj = out.getvalue()
    return bytes_obj

def optimize_jpg(srcfname, dstfname):
    if OPTJPG_CMD is not None:
        print(OPTJPG_CMD+" '"+srcfname+"' > '"+dstfname+"'")
        os.system(OPTJPG_CMD+" '"+srcfname+"' > '"+dstfname+"'")
    else:
        print("cp '"+srcfname+"' '"+dstfname+"'")
        shutil.copy(srcfname, dstfname)

def convert_to_jpg(srcfname, dstfname):
    print("convert '"+srcfname+"' -quality 85 -format jpg 'jpg:"+dstfname+"nopt'")
    os.system("convert '"+srcfname+"' -quality 85 -format jpg 'jpg:"+dstfname+"nopt'")
    optimize_jpg(dstfname+"nopt", dstfname)
    print("rm '"+dstfname+"nopt'")
    os.system("rm '"+dstfname+"nopt'")

def process_image(ig, iginfo, imginfo):
    s3prefix = IMG_OUTPUT_PATH+getS3FolderPrefix(iginfo['w'])
    imagesprefix = s3prefix+'images/'+iginfo['w']+'-'+getS3FolderIG(ig)+'/'
    
    os.makedirs(imagesprefix, exist_ok=True)
    # if source image is not jpeg, encode it in jpeg:
    ext = imginfo['fsfn'].lower()[-4:]
    if ext == "jpeg" or ext == ".jpg":
        optimize_jpg(imginfo['fsfn'], imagesprefix+imginfo['s3fn'])
    else:
        convert_to_jpg(imginfo['fsfn'], imagesprefix+imginfo['s3fn'])  

def copy_sources():
    wfolderinfos = get_source_folders()
    print(wfolderinfos)
    for w, wpath in wfolderinfos.items():
        s3prefix = IMG_OUTPUT_PATH+getS3FolderPrefix(w)
        sourcesprefix = s3prefix+'sources/'
        os.makedirs(sourcesprefix, exist_ok=True)
        # copy source images
        print("rm -rf '"+sourcesprefix+wpath+"'")
        shutil.rmtree(sourcesprefix+wpath, ignore_errors=True)
        print("cp -R '"+IMG_INPUT_PATH+wpath+"' '"+sourcesprefix+wpath+"'")
        shutil.copytree(IMG_INPUT_PATH+wpath, sourcesprefix+wpath)

def process_images():
    iginfos = get_iginfos()
    for ig, iginfo in iginfos.items():
        imagesprefix = IMG_OUTPUT_PATH+getS3FolderPrefix(iginfo['w'])+'images/'+iginfo['w']+'-'+getS3FolderIG(ig)+'/'
        manifest = []
        for imginfo in iginfo['il']:
            process_image(ig, iginfo, imginfo)
            manifest.append(ildatafromfsfn(imginfo['fsfn'], imginfo['s3fn']))
        manifest_str = json.dumps(manifest)
        manifest_gzip = gzip_str(manifest_str)
        with open(imagesprefix+"dimensions.json", "wb") as df:
            df.write(manifest_gzip)

if __name__ == '__main__':
    copy_sources()
    process_images()