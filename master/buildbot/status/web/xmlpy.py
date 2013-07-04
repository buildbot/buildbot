
#import library to do http requests:
import urllib2
 
#import easy to use xml parser called minidom:
from xml.dom.minidom import parseString
#all these imports are standard on most modern python implementations
 
#download the file:
file = urllib2.urlopen('http://localhost:8001/test.xml')
#convert to string:
data = file.read()
#close file because we dont need it anymore:
file.close()
#parse the xml you downloaded
dom = parseString(data)
#retrieve the first xml tag (<tag>data</tag>) that the parser finds with name tagName:
xmlTag = dom.getElementsByTagName('test-suite')

atr = xmlTag[0]

a = atr.attributes["time"] 

#strip off the tag (<tag>data</tag>  --->   data):
#xmlData=xmlTag.replace('<test-case>','').replace('</test-case>','')
#print out the xml tag and data in this format: <tag>data</tag>
#print xmlTag
#just print the data
#print xmlData

print atr.attributes["time"]
print a.value