#!/usr/bin/env python
# -*- coding: utf-8 -*-
# by Karl Wachs
# feb 3 2016
# version 0.5 
##
##	check logfiles sizes and manage
import urllib
import json
import urlparse
import os
import time
import piBeaconUtils   as U
import piBeaconGlobals as G
import sys

from BaseHTTPServer import BaseHTTPRequestHandler
from BaseHTTPServer import HTTPServer

class GetHandler(BaseHTTPRequestHandler):

	def do_HEAD(self):
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
 
	def do_GET(self):
		global pid, defaults, regularOutputFile
		global defaultsExtra, extraOutputFile, webServerInputHTML, extraInputFile
		global lastCommand, ignoreCashedEntry
		x = self.wfile.write
		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		x('<!DOCTYPE html>')
		x('<html>')
		x('<meta http-equiv="Pragma" content="no-cache">')
		x('<meta http-equiv="Expires" content="-1″>')
		x('<meta http-equiv="CACHE-CONTROL" content="NO-CACHE">')
		x(	'<head>')
		x(		'<h3 style="background-color:rgb(30, 0, 30); color:rgb(0, 255, 0); font-family:Courier; "><b>Enter parameters, eg SID and pass-code for your WiFi, ... </b></h3>')
		x(	'</head>')

		x(	'<body style="background-color:rgb(30, 0, 30); font-family:Courier; color:rgb(0, 255, 0);">')
		x(		'<form action = "/cgi-bin/get_UID_etc.cgi" method = "get" id="myForm">'+
					'<hr size=4 width="100%">'+
					'SSID................:  <input type = "text" name = "SSID"     value = "do+not+change" maxlength = "35" /> <br> '+
					'passCode............:  <input type = "text" name = "passCode" value = "do+not+change" maxlength = "35" />  <br>')
		x(			'. . . . . . . . . . .<br>')
		x(			'Time Zone...........:  <select name="timezone">'+
						'<option value="99">do+not+change+time+zone</option>'+
						'<option value="12">Pacific/Auckland(+12)</option>'+
						'<option value="11">Pacific/Pohnpei (+11)</option>'+
						'<option value="10">Australia/Melbourne (+10)</option>'+
						'<option value="9">Asia/Tokyo (+9)</option>'+
						'<option value="8">Asia/Shanghai (+8)</option>'+
						'<option value="7">Asia/Saigon (+7)</option>'+
						'<option value="6">Asia/Dacca (+6)</option>'+
						'<option value="5">Asia/Karachi (+5)</option>'+
						'<option value="4">Asia/Dubai (+4)</option>'+
						'<option value="3">/Europe/Moscow (+3)</option>'+
						'<option value="2">/Europe/Helsinki (+2)</option>'+
						'<option value="1">Central-EU (+1)</option>'+
						'<option value="0">UK (GMT) </option>'+
						'<option value="-5">US-East Coast (-5)</option>'+
						'<option value="-6">US-Central (-6)</option>'+
						'<option value="-7">US-Mountain< (-7)/option>'+
						'<option value="-8">US-West Coast(-8)</option>'+
						'<option value="-9">US-Alaska (-9)</option>'+
						'<option value="-10">Pacific/Honolulu (-10)</option>'+
						'<option value="-11">US-Samoa (-11)</option>'+
					'</select> <br>')
		x(			'<br>')
#		x(			'then--------------==> <input type = "submit" value = "Submit General Parameters" />')
		x(			'then--------------==> <input type="button" onclick="submit()" value="Submit General Parameters"/>')

		getwebServerInputHTML()
		if webServerInputHTML != "":
			x(webServerInputHTML)

		x(		'<hr size=4 width="100%">')
		x(		'</form>')
		x(		'<script>')
		x(		'	function submit() {')
		x(		'	  /*Put all the data posting code here*/')
		x(		'	 document.getElementById("myForm").reset();')
		x(		'		}')
		x(		'</script>')
 
		x(	'</body>')
		x('</html>')

		items =  urlparse.urlparse(self.path)
		if len(items) < 5: 		 return 
		if len(items.query) < 5: return 
		items = urllib.unquote(items.query)
		items = (items).split("&")
		U.logger.log(10,"1. #items:{}, #ofparamets expected:{}; items{}".format(len(items),len(defaultsExtra)+ len(defaults), items))

	
		output = {}
		extraData = ""
		for item1 in items:
			item = item1.split("=")
			if len(item) !=2: continue
			# skip input after start to not repeat submit of last cashed values
			if False:
				if item[0] not in lastCommand:
					lastCommand[item[0]] = ""
					continue
			lastCommand[item[0]] = item[1] 
			if   item[0] in defaults and item[1] != defaults[item[0]] and len(item[1]) > 0: 
				output[item[0]] = item[1]
			if   item[0] in defaultsExtra and item[1] != defaultsExtra[item[0]] and len(item[1]) > 0: 
				extraData += item[1]+";"
		extraData =  extraData.strip(";")
		U.logger.log(20,"2. general:{} + extraData:{}".format(output, extraData))

		for item in output:
			if output[item] != "":
				f=open(regularOutputFile,"w")
				f.write(json.dumps(output))
				f.close()
				break

		if extraData !="" and extraOutputFile !="":
			U.logger.log(20,"writing to extraData file:{} cmd:>{}<".format(extraOutputFile, extraData))
			f=open(extraOutputFile,"w")
			f.write(extraData)
			f.close()

		##subprocess.call("kill -9 "+str(pid), shell=True)
		
		
def getwebServerInputHTML(init=False):
	global  defaultsExtra, extraOutputFile, webServerInputHTML, extraInputFile

	if init:
		defaultsExtra 		= {}
		webServerInputHTML  = []
		extraOutputFile  	= ""
	if os.path.isfile(extraInputFile):
		f = open(extraInputFile,"r")
		ddd = f.read()
		f.close()
		try: theDict = json.loads(ddd)
		except: 
			U.logger.log(20,"no new extra input file: {}".format(ddd))
			return 
		try: 	defaultsExtra 		= theDict["defaults"]
		except: defaultsExtra		= {} 
									#{"autoupdate":"-1","re":"-1","speed":"-1","mode":"-1","led":"-1","LED":"-1","calibrate":"-1","lightSensor":"-1","lightoff":"-1","offsetArm":"0","goto":"-1","cmd":"none","leftrightcalib":"-1"}
		try: 	webServerInputHTML  = theDict["webServerInputHTML"]
		except:	webServerInputHTML	= ""

		try: 	extraOutputFile  	= theDict["outputFile"]
		except:	extraOutputFile		= ""
		U.logger.log(10,"read new params:  to theDict {}".format(theDict))


global pid, defaults, regularOutputFile, inputFile
global lastCommand, ignoreCashedEntry

lastCommand ={}
extraInputFile 		= G.homeDir+"temp/webserverINPUT.show"
regularOutputFile	= G.homeDir+"temp/webparameters.input"
port = 8000

G.program = "webserverINPUT"
U.setLogging()

defaults		= {"SSID":"do+not+change", "timezone":"99","passCode":"do+not+change"}
try:
	ipNumber	= sys.argv[1]
	port		= int(sys.argv[2])
	regularOutputFile		= sys.argv[3]

except: 
	U.logger.log(30,"Starting web server not working, no ip port # given, command:{}".format(sys.argv))
	exit()

getwebServerInputHTML(init=True)


U.logger.log(20,"Starting web server with IP#:{}:{}  regular-output file:{}, extra-Data:{}".format(ipNumber, port, regularOutputFile, extraOutputFile))



pid =  os.getpid()

U.killOldPgm(str(pid),"webserverINPUT.py")
time.sleep(0.5)


server = HTTPServer(('', port), GetHandler)
U.logger.log(30,"Starting server, access at {}:{}".format(ipNumber,port))
server.serve_forever()
