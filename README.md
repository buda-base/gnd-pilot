# Pilot of Gandhari image import


## Sync with BUDA

Export the sheets of [the catalog spreadsheet](https://docs.google.com/spreadsheets/d/1nFTW0dZOhkWCgWXpk8UF8WHEwW67xJlO1E8lLR5BXKw/edit#gid=577303632) to csv in the `input/` folder, and copy all the images in the `images/` folder. Then run:

```sh
$ python3 processimages.py
$ aws s3 sync s3/Works/ s3://archive.tbrc.org/Works/
$ python3 processdata.py
$ curl -X PUT -H Content-Type:text/turtle -T GND.ttl -K curlcredentials.txt -G http://fuseki.bdrc.io/fuseki/corerw/data --data-urlencode 'graph=http://purl.bdrc.io/graph/GND'
```
