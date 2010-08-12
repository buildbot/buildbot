'''
Created on Aug 9, 2010

@author: meloam
'''
import unittest
import time
import calendar
import datetime
import re
class fixedOffset(datetime.tzinfo):
    """
    fixed offset timezone
    """
    def __init__(self, minutes, hours, offsetSign = 1):
        self.minutes = int(minutes) * offsetSign
        self.hours   = int(hours)   * offsetSign
        self.offset  = datetime.timedelta(minutes = self.minutes,
                                         hours   = self.hours)

    def utcoffset(self, dt):
        return self.offset

    def dst(self, dt):
        return datetime.timedelta(0)
    

class Test(unittest.TestCase):
    
    def test1Hour(self):
        self.assertEqual( self.convertTime("1970-01-01T00:00:00+00:00"), 0)
        self.assertEqual( self.convertTime("1970-01-01T00:00:00+01:00"), -3600 )
        self.assertEqual( self.convertTime("1970-01-01T00:00:00-01:00"), 3600 )
        self.assertEqual( self.convertTime("1970-01-01T00:00:00-02:00"), 7200 )
        self.assertEqual( self.convertTime("1970-01-01T00:00:01+00:00"), 1)
        self.assertEqual( self.convertTime("1970-01-01T00:00:01+01:00"), 1 - 60 * 60)
 
    def convertTime(self, myTestTimestamp):
        #"1970-01-01T00:00:00+00:00"
        matcher = re.compile(r'(\d\d\d\d)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)([-+])(\d\d):(\d\d)')
        result  = matcher.match(myTestTimestamp)
        (year, month, day, hour, minute, second, offsetsign, houroffset, minoffset) = \
            result.groups()
        if offsetsign == '+':
            offsetsign = 1
        else:
            offsetsign = -1
        
        offsetTimezone = fixedOffset( minoffset, houroffset, offsetsign )
        myDatetime = datetime.datetime( int(year),
                                        int(month),
                                        int(day),
                                        int(hour),
                                        int(minute),
                                        int(second),
                                        0,
                                        offsetTimezone)
        return calendar.timegm( myDatetime.utctimetuple() )
      
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()