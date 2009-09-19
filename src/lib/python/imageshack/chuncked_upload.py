#!/usr/bin/env python

'''
Client API library for chuncked images and videos uploading to imageshack.us

Using "Streaming upload API" as described here:

http://code.google.com/p/imageshackapi/wiki/StreamingAPI

'''

import os
import urllib
import httplib
import urllib2
from urlparse import urlparse

from os.path import exists
from urlparse import urlsplit
from mimetypes import guess_type
from xml.dom.minidom import parse 
from xml.dom.minidom import parseString

HTTP_UPLOAD_TIMEOUT = 300
BLOCK_SIZE=1024
SERVER='render1.imageshack.us:8080'
PATH='/renderapi'
ENDPOINT='http://'+SERVER+PATH


class UploadException(Exception):
    ''' Exceptions of this class are raised for various upload based errors '''
    pass


class ServerException(Exception):
    ''' Exceptions of this class are raised for upload errors reported by server '''
    
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __str__(self):
        return "ServerException:%s:%s" % (self.code, self.message)


class Uploader:
    ''' Class to upload images and video to imageshack.
    '''
    
    def __init__(self, dev_key, cookie=None, username=None, password=None, timeout=HTTP_UPLOAD_TIMEOUT):
        '''Creates uploader object.
        Args:
        dev_key: developer key (mandatory)
        cookie: imagesack user cookie (optional)
        username,password: imageshack user account credentials (optional)
        timeout: timeout in seconds for upload operation (optional)
        '''
        self.cookie = cookie
        self.username = username
        self.password = password
        self.dev_key = dev_key
        self.timeout = timeout
            
    def start(self, filename, tags = [], public = True):
        '''Request file upload URL from server
        '''
        data = {'filename' : filename}
        data['key'] = self.dev_key         
        if self.cookie is not None:    
            data['cookie'] = self.cookie
        if tags:
            data['tags'] = ','.join(tags)    
        data['public'] = True if public else False
        if self.username is not None:
            data['a_username'] = self.username
        if self.password is not None:
            data['a_password'] = self.password

        #try:
        req = urllib2.urlopen(ENDPOINT+'/start', urllib.urlencode(data))
        xml = req.read()
        #except:
        #    raise UploadException('Could not connect to server')
        try:
            dom = parseString(xml)
            url = dom.documentElement.getAttribute('putURL')
        except:
            raise ServerException('Wrong server response')
        dom.unlink()
        req.close()
        return url
    
    def get_length(self, url):
        uuid = url.split('/')[-1]
        try:
            conn = httplib.HTTPConnection(SERVER)
            conn.request("HEAD", PATH + '/put/' + uuid)
            res = conn.getresponse()
        except:
            raise UploadException('Could not connect to server')
        try:
            size = int(res.getheader('Content-Length'))
        except:
            raise ServerException('Wrong server headers response')
        return size
    
    def upload_file(self, filename, tags = [], public = True, end = -1):
        '''Upload file to ImageShack using streaming API
        Args:
        end: last byte number that will be uploaded.
        If end is -1, file will be uploaded to the end.
        '''
        url = self.start(filename, tags, public)
        return self.upload_range(filename, url, 0, -1)
        
    def resume_upload(self, filename, url, end = -1):
        size = self.get_length(url)
        return self.upload_range(filename, url, size, end)
        
    def upload_range(self, filename, url, begin = 0, end = -1):
        '''Upload file to server.
        Args:
        url: upload url (get one using start method)
        begin: first byte number
        end: last byte number (if -1, end is file size)
        ''' 
        purl = urlparse(url)
        current_byte = begin
        filelen = os.path.getsize(filename)
        if end == -1: end = filelen
        if end > filelen: end = filelen
        try:
            conn = httplib.HTTPConnection(SERVER)
            conn.connect()
            conn.putrequest('PUT', "%s" % purl.path)
            range_str="bytes %d-%d/%d" % (begin, end, filelen)
            conn.putheader('Content-range', range_str)
            conn.putheader('Content-type', 'application/octet-stream')
            conn.putheader('Content-length', (end - begin) + 1)
            conn.endheaders()
        except:
            raise UploadException('Could not connect to server')

        try: fileobj = open(filename, 'rb')
        except: raise UploadException('Could not open file')
        try: fileobj.seek(begin)
        except: raise UploadException('Could not seek file')
        
        while current_byte < end:
            try: data = fileobj.read(BLOCK_SIZE)
            except: raise UploadException('File I/O error')
            try: conn.send(data)
            except: raise UploadException('Could not send data')
            current_byte += len(data)
        print 'sent data'
        fileobj.close()
        
        try:
            print 'waiting for response'
            resp = conn.getresponse()
            print 'reading response'
            res = resp.read()
        except:
            raise UploadException('Could not get server response')
        
        return (resp.status, resp.reason, res)
